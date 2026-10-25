from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.deal_page import get_deals_page_url, render_deals_page, write_deals_page
from src.models import EvaluatedDeal, FlightOffer
from src.notifiers.discord import DiscordNotifier


def _deal() -> EvaluatedDeal:
    offer = FlightOffer(
        origin="MUC",
        origin_name="München",
        destination="LIS",
        destination_name="<Lissabon>",
        destination_country="Portugal",
        outbound_date="2026-11-12",
        inbound_date="2026-11-19",
        price_eur=89.0,
        airline="TAP",
        provider="travelpayouts",
        booking_url="https://example.com/book",
        is_wishlist=True,
    )
    return EvaluatedDeal(
        offer=offer,
        threshold_eur=115.0,
        historical_avg_eur=160.0,
        discount_vs_avg_percent=44.0,
        discount_vs_threshold_percent=22.6,
        deal_score=90.0,
        reason="<40% unter dem Durchschnitt>",
        exclude_url="https://github.com/example/repo/issues/new?title=exclude%3ALIS",
    )


def test_get_deals_page_url_uses_repository_and_custom_url() -> None:
    assert get_deals_page_url("owner/flight-deals") == "https://owner.github.io/flight-deals/"
    assert get_deals_page_url("owner/owner.github.io") == "https://owner.github.io/"
    assert get_deals_page_url(configured_url="https://example.com/deals///?ignored=yes") == (
        "https://example.com/deals/"
    )
    assert get_deals_page_url(configured_url="http://example.com/deals") == ""
    assert get_deals_page_url(configured_url="https://user@example.com/deals") == ""


def test_render_deals_page_escapes_text_and_disables_unsafe_links() -> None:
    deal = _deal()
    deal.offer.booking_url = "javascript:alert(1)"
    page = render_deals_page([deal], datetime(2026, 1, 2, tzinfo=timezone.utc))

    assert "<Lissabon>" not in page
    assert "&lt;Lissabon&gt;" in page
    assert "&lt;40% unter dem Durchschnitt&gt;" in page
    assert 'href="javascript:alert(1)"' not in page
    assert 'class="button button-disabled"' in page
    assert 'href="https://github.com/example/repo/issues/new?title=exclude%3ALIS"' in page
    assert "02.01.2026 00:00 UTC" in page


def test_write_deals_page_creates_parent_directory(tmp_path: Path) -> None:
    destination = tmp_path / "site" / "index.html"

    write_deals_page([_deal()], destination)

    assert destination.is_file()
    assert "1 Schnäppchen gefunden" in destination.read_text(encoding="utf-8")


def test_discord_deal_summary_sends_one_message(monkeypatch) -> None:
    calls = []

    def post(url, *, json, timeout):
        calls.append((url, json, timeout))
        return SimpleNamespace(status_code=204)

    monkeypatch.setattr("src.notifiers.discord.requests.post", post)
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")

    assert notifier.send_deal_summary([_deal(), _deal()], "https://owner.github.io/repo/")
    assert len(calls) == 1
    assert calls[0][1]["content"].count("gefunden!") == 1
    assert calls[0][1]["content"].endswith("(https://owner.github.io/repo/)")
    assert "embeds" not in calls[0][1]


def test_discord_deal_summary_rejects_invalid_page_url(monkeypatch) -> None:
    def unexpected_post(*args, **kwargs):
        raise AssertionError("Discord must not receive a request for an invalid page URL")

    monkeypatch.setattr("src.notifiers.discord.requests.post", unexpected_post)
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")

    assert not notifier.send_deal_summary([_deal()], "https://")
