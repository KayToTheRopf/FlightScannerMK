from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.compat import yaml_mod as yaml

from src.analyzer import DealAnalyzer, build_exclude_issue_url
from src.handle_feedback import parse_and_execute_feedback
from src.models import EvaluatedDeal, FlightOffer
from src.notifiers.discord import DiscordNotifier, MAX_EMBED_TEXT_PER_MESSAGE
from src.notifiers.github_issue import GitHubIssueNotifier


def _sample_config() -> dict:
    return {
        "departure_airports": [
            {"code": "FMM", "name": "Memmingen", "max_explore_price_eur": 55.0},
            {"code": "MUC", "name": "München", "max_explore_price_eur": 120.0},
        ],
        "search_window": {
            "months_ahead": 6,
            "min_stay_days": 3,
            "max_stay_days": 14,
            "max_stops": 1,
        },
        "deal_scoring": {
            "min_discount_vs_history_percent": 25.0,
            "first_seen_margin_percent": 10.0,
            "notification_cooldown_days": 7,
            "max_deals_per_run": 10,
        },
        "wishlist_destinations": [
            {"code": "PMI", "name": "Palma de Mallorca", "country": "Spanien", "max_price_eur": 65.0},
            {"code": "LIS", "name": "Lissabon", "country": "Portugal", "max_price_eur": 115.0},
        ],
    }


def test_deal_analyzer_filters_and_scores(tmp_path: Path) -> None:
    bl_path = tmp_path / "blacklist.json"
    hist_path = tmp_path / "price_history.json"

    bl_path.write_text(
        json.dumps({"excluded_airports": ["TIA"], "excluded_cities": [], "excluded_countries": []}),
        encoding="utf-8",
    )
    hist_path.write_text(
        json.dumps(
            {
                "routes": {
                    "MUC-LIS": {
                        "destination_name": "Lissabon",
                        "avg_price_eur": 160.0,
                        "min_price_eur": 120.0,
                        "max_price_eur": 210.0,
                        "observations": 5,
                    }
                },
                "notified_deals": {},
            }
        ),
        encoding="utf-8",
    )

    analyzer = DealAnalyzer(_sample_config(), bl_path, hist_path, repo_slug="user/flight-deals")

    offers = [
        # 1. Blacklisted (TIA) -> muss herausgefiltert werden
        FlightOffer(
            origin="FMM",
            origin_name="Memmingen",
            destination="TIA",
            destination_name="Tirana",
            destination_country="Albanien",
            outbound_date="2026-11-10",
            inbound_date="2026-11-15",
            price_eur=29.99,
            airline="Ryanair",
            provider="ryanair",
        ),
        # 2. Zu kurzer Aufenthalt (1 Tag) -> muss herausgefiltert werden
        FlightOffer(
            origin="FMM",
            origin_name="Memmingen",
            destination="PMI",
            destination_name="Palma de Mallorca",
            destination_country="Spanien",
            outbound_date="2026-11-10",
            inbound_date="2026-11-11",
            price_eur=35.0,
            airline="Ryanair",
            provider="ryanair",
        ),
        # 3. Echtes Wunschziel-Schnäppchen ab MUC nach LIS (89 EUR vs 160 EUR historisch)
        FlightOffer(
            origin="MUC",
            origin_name="München",
            destination="LIS",
            destination_name="Lissabon",
            destination_country="Portugal",
            outbound_date="2026-11-12",
            inbound_date="2026-11-19",
            price_eur=89.0,
            airline="TAP",
            provider="travelpayouts",
            is_wishlist=True,
        ),
        # 4. Echtes Explore-Schnäppchen ab FMM nach ZAD (34 EUR bei Limit 55 EUR)
        FlightOffer(
            origin="FMM",
            origin_name="Memmingen",
            destination="ZAD",
            destination_name="Zadar",
            destination_country="Kroatien",
            outbound_date="2026-11-14",
            inbound_date="2026-11-18",
            price_eur=34.0,
            airline="Ryanair",
            provider="ryanair",
        ),
    ]

    deals = analyzer.evaluate_offers(offers)
    assert len(deals) == 2
    # Wunschziel LIS mit hoher historischer Ersparnis sollte auf Platz 1 stehen
    assert deals[0].offer.destination == "LIS"
    assert "unter Ø-Routenpreis" in deals[0].reason
    assert "ignore-deal%3AMUC-LIS" in deals[0].exclude_url

    # Cooldown-Test: Nach dem Markieren darf derselbe Deal im nächsten Lauf nicht sofort wieder erscheinen
    analyzer.mark_deals_notified(deals)
    analyzer.save_history()

    deals_second_run = analyzer.evaluate_offers(offers)
    assert len(deals_second_run) == 0


def test_feedback_handler_updates_blacklist_and_wishlist(tmp_path: Path) -> None:
    bl_path = tmp_path / "blacklist.json"
    cfg_path = tmp_path / "search_config.yaml"

    bl_path.write_text(
        json.dumps({"excluded_airports": [], "excluded_cities": [], "excluded_countries": []}),
        encoding="utf-8",
    )
    cfg_path.write_text(yaml.safe_dump(_sample_config(), allow_unicode=True), encoding="utf-8")

    # Test 1: 1-Klick-Exclude Issue Titel ("exclude:STN") + Kommentar ("/exclude city:Tirana" + "/watch ATH 90 Name=Athen")
    feedback_input = "exclude:STN\n/exclude city:Tirana\n/exclude country:Albanien\n/watch ATH 90 Name=Athen"
    messages = parse_and_execute_feedback(feedback_input, blacklist_path=bl_path, config_path=cfg_path)
    assert len(messages) == 4

    updated_bl = json.loads(bl_path.read_text(encoding="utf-8"))
    assert "STN" in updated_bl["excluded_airports"]
    assert "Tirana" in updated_bl["excluded_cities"]
    assert "Albanien" in updated_bl["excluded_countries"]

    updated_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    codes = {w["code"]: w["max_price_eur"] for w in updated_cfg["wishlist_destinations"]}
    assert codes["ATH"] == 90.0

    # Test 2: Deal ausschließen und anschließend Ort & Deal wieder freigeben (unexclude)
    deal_ex_path = tmp_path / "deal_exclusions.json"
    un_input = (
        "ignore-deal:FMM-BNX:2026-12-05:2026-12-11\n"
        "unexclude:STN\n"
        "/unexclude Tirana\n"
        "unexclude-deal:FMM-BNX:2026-12-05:2026-12-11"
    )
    un_messages = parse_and_execute_feedback(
        un_input,
        blacklist_path=bl_path,
        config_path=cfg_path,
        deal_exclusions_path=deal_ex_path,
    )
    assert len(un_messages) == 4
    bl_after = json.loads(bl_path.read_text(encoding="utf-8"))
    assert "STN" not in bl_after["excluded_airports"]
    assert "Tirana" not in bl_after["excluded_cities"]
    assert "Albanien" in bl_after["excluded_countries"]
    deal_ex_after = json.loads(deal_ex_path.read_text(encoding="utf-8"))
    assert deal_ex_after["excluded_signatures"] == []

    # Test 3: Wunschziel per 1-Klick-Titel hinzufügen/ändern ("watch:LIS:105:Lissabon") und entfernen ("unwatch:ATH")
    watch_messages = parse_and_execute_feedback(
        "watch:LIS:105:Lissabon\nunwatch:ATH",
        blacklist_path=bl_path,
        config_path=cfg_path,
    )
    assert len(watch_messages) == 2
    cfg_after_watch = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    codes_after = {w["code"]: w["max_price_eur"] for w in cfg_after_watch["wishlist_destinations"]}
    assert codes_after["LIS"] == 105.0
    assert "ATH" not in codes_after


def test_feedback_handler_pause_and_resume(tmp_path: Path) -> None:
    from datetime import date
    from src.handle_feedback import get_pause_until

    bl_path = tmp_path / "blacklist.json"
    cfg_path = tmp_path / "search_config.yaml"

    bl_path.write_text(
        json.dumps({"excluded_airports": [], "excluded_cities": [], "excluded_countries": []}),
        encoding="utf-8",
    )
    cfg_path.write_text(yaml.safe_dump(_sample_config(), allow_unicode=True), encoding="utf-8")

    ref_today = date(2026, 11, 2)
    assert get_pause_until(cfg_path, today=ref_today) is None

    # 1) Für 7 Tage pausieren per Kommentar
    msgs = parse_and_execute_feedback("/pause 7d", blacklist_path=bl_path, config_path=cfg_path, today=ref_today)
    assert len(msgs) == 1
    assert get_pause_until(cfg_path, today=ref_today) == "2026-11-09"
    # Nach Ablauf der Pause (am 10.11.) automatisch wieder aktiv
    assert get_pause_until(cfg_path, today=date(2026, 11, 10)) is None

    # 2) Bis festes Datum pausieren per Issue-Titel
    msgs = parse_and_execute_feedback("pause: 2026-12-01", blacklist_path=bl_path, config_path=cfg_path, today=ref_today)
    assert len(msgs) == 1
    assert get_pause_until(cfg_path, today=ref_today) == "2026-12-01"

    # 3) Sofort wieder fortsetzen per /resume
    msgs = parse_and_execute_feedback("/resume", blacklist_path=bl_path, config_path=cfg_path, today=ref_today)
    assert len(msgs) == 1
    assert get_pause_until(cfg_path, today=ref_today) is None

    # 4) Test-Discord anfordern per "test-discord" / "/test-discord"
    msgs_discord = parse_and_execute_feedback("test-discord", blacklist_path=bl_path, config_path=cfg_path, today=ref_today)
    assert len(msgs_discord) == 1
    cfg_after_discord = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert cfg_after_discord.get("force_next_discord") is True


def test_github_markdown_report_contains_exclude_link() -> None:
    offer = FlightOffer(
        origin="FMM",
        origin_name="Memmingen",
        destination="PMI",
        destination_name="Palma de Mallorca",
        destination_country="Spanien",
        outbound_date="2026-11-10",
        inbound_date="2026-11-17",
        price_eur=39.99,
        airline="Ryanair",
        provider="ryanair",
        is_wishlist=True,
    )
    from src.models import EvaluatedDeal

    deal = EvaluatedDeal(
        offer=offer,
        threshold_eur=65.0,
        historical_avg_eur=75.0,
        discount_vs_avg_percent=46.7,
        discount_vs_threshold_percent=38.5,
        deal_score=66.7,
        reason="47% unter Ø-Routenpreis (75 €)",
        exclude_url=build_exclude_issue_url("user/repo", "PMI", "Palma de Mallorca", "Spanien"),
    )
    md = GitHubIssueNotifier.format_markdown_report([deal])
    assert "Palma de Mallorca" in md
    assert "🚫 Deal ausschließen" in md
    assert "exclude%3APMI" in md


def test_discord_splits_embeds_to_respect_message_size_limit(monkeypatch) -> None:
    deals = []
    for index in range(10):
        offer = FlightOffer(
            origin="FMM",
            origin_name="Memmingen",
            destination=f"AAA{index}",
            destination_name=f"Destination {index}",
            destination_country="X" * 900,
            outbound_date="2026-11-10",
            inbound_date="2026-11-17",
            price_eur=39.99,
            airline="Ryanair",
            provider="ryanair",
            booking_url="https://example.test/flight",
        )
        deals.append(
            EvaluatedDeal(
                offer=offer,
                threshold_eur=65.0,
                historical_avg_eur=None,
                discount_vs_avg_percent=None,
                discount_vs_threshold_percent=38.5,
                deal_score=43.5,
                reason="38% unter Preisgrenze",
            )
        )

    sent_payloads = []

    def post(_url, *, json, timeout):
        sent_payloads.append(json)
        return SimpleNamespace(status_code=204)

    monkeypatch.setattr("src.notifiers.discord.requests.post", post)

    assert DiscordNotifier("https://example.test/webhook").send_deals(deals)
    assert len(sent_payloads) > 1
    sent_embeds = []
    for payload in sent_payloads:
        embeds = payload["embeds"]
        assert len(embeds) <= 10
        assert sum(len(embed["title"]) + len(embed["description"]) for embed in embeds) <= MAX_EMBED_TEXT_PER_MESSAGE
        sent_embeds.extend(embeds)
    assert len(sent_embeds) == len(deals)
