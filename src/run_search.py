from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

import yaml

from src.analyzer import DealAnalyzer
from src.deal_page import get_deals_page_url, write_deals_page
from src.models import EvaluatedDeal, FlightOffer
from src.notifiers.discord import DiscordNotifier
from src.notifiers.email_smtp import EmailSmtpNotifier
from src.notifiers.github_issue import GitHubIssueNotifier
from src.providers.google_flights import GoogleFlightsProvider
from src.providers.ryanair import RyanairProvider
from src.providers.travelpayouts import TravelpayoutsProvider

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "search_config.yaml"
DEFAULT_BLACKLIST_PATH = ROOT_DIR / "config" / "blacklist.json"
DEFAULT_HISTORY_PATH = ROOT_DIR / "data" / "price_history.json"
DEFAULT_DEALS_PAGE_PATH = ROOT_DIR / "site" / "index.html"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_all_offers(config: dict) -> List[FlightOffer]:
    offers: List[FlightOffer] = []

    # 1. Ryanair FareFinder API (Live-Preise, perfekt für Memmingen FMM & Low-Cost)
    ryanair = RyanairProvider()
    offers.extend(ryanair.search_deals(config))

    # 2. Travelpayouts / Aviasales Data API (Überallhin-Cache für München MUC & FMM)
    travelpayouts = TravelpayoutsProvider()
    tp_offers = travelpayouts.search_deals(config)

    # 3. Google Flights (fast-flights) für feste Wunschziele + optionale Live-Verifizierung von Travelpayouts-Treffern
    google_flights = GoogleFlightsProvider()
    offers.extend(google_flights.search_deals(config))

    verify_tp = config.get("providers", {}).get("travelpayouts", {}).get("verify_with_google_flights", True)
    max_stops = int(config.get("search_window", {}).get("max_stops", 1))

    if tp_offers and verify_tp and config.get("providers", {}).get("google_flights", {}).get("enabled", True):
        # Verifiziere die bis zu 8 günstigsten Travelpayouts-Kandidaten live via Google Flights
        tp_sorted = sorted(tp_offers, key=lambda o: o.price_eur)
        verified_count = 0
        for cand in tp_sorted:
            if verified_count >= 8:
                offers.append(cand)
                continue
            live = google_flights.verify_cached_offer(cand, max_stops=max_stops)
            verified_count += 1
            if live is not None:
                offers.append(live)
            else:
                offers.append(cand)
    else:
        offers.extend(tp_offers)

    return offers


def dispatch_notifications(config: dict, deals: List[EvaluatedDeal], dry_run: bool = False) -> int:
    if not deals:
        logging.info("Keine neuen echten Schnäppchen in diesem Durchlauf gefunden.")
        return 0

    # Konsolen-Übersicht immer ausgeben (hilfreich in GitHub Actions Logs & lokal)
    print("\n" + "=" * 85)
    print(f"GEFUNDENE ECHTE FLUGSCHNÄPPCHEN ({len(deals)} Treffer)")
    print("=" * 85)
    for idx, d in enumerate(deals, start=1):
        o = d.offer
        tag = "[WUNSCHZIEL]" if o.is_wishlist else "[EXPLORE]   "
        print(
            f"{idx:2d}. {tag} {o.origin} -> {o.destination_name} ({o.destination}, {o.destination_country}) | "
            f"{o.outbound_date} bis {o.inbound_date} ({o.stay_days}T) | "
            f"{o.price_eur:6.2f} EUR ({d.reason}) | {o.airline} [{o.provider}]"
        )
    print("=" * 85 + "\n")

    if dry_run:
        logging.info("Dry-Run aktiv: Überspringe externe Benachrichtigungen (Discord/GitHub/Mail).")
        return 0

    notif_cfg = config.get("notifications", {})
    sent_channels = 0

    if notif_cfg.get("discord", {}).get("enabled", True):
        page_url = get_deals_page_url(configured_url=os.getenv("FLIGHT_DEALS_PAGE_URL", ""))
        if DiscordNotifier().send_deal_summary(deals, page_url):
            sent_channels += 1

    if notif_cfg.get("github_issue", {}).get("enabled", True):
        label = notif_cfg.get("github_issue", {}).get("issue_label", "flight-deal")
        if GitHubIssueNotifier(label=label).send_deals(deals):
            sent_channels += 1

    if notif_cfg.get("email", {}).get("enabled", False):
        if EmailSmtpNotifier().send_deals(deals):
            sent_channels += 1

    return sent_channels


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automatische Flugpreis- & Schnäppchen-Suche (MUC & FMM)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Pfad zur search_config.yaml")
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_BLACKLIST_PATH, help="Pfad zur blacklist.json")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH, help="Pfad zur price_history.json")
    parser.add_argument("--dry-run", action="store_true", help="Führt Suche & Bewertung aus, sendet aber keine Nachrichten")
    parser.add_argument("--verbose", action="store_true", help="Detailliertes Debug-Logging aktivieren")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args.config)
    analyzer = DealAnalyzer(
        config=config,
        blacklist_path=args.blacklist,
        history_path=args.history,
    )

    offers = collect_all_offers(config)
    logging.info("Insgesamt %d Flugangebote über alle aktiven Provider gesammelt.", len(offers))

    deals = analyzer.evaluate_offers(offers)
    logging.info("%d Angebote als echte Schnäppchen eingestuft.", len(deals))

    if not args.dry_run:
        write_deals_page(deals, DEFAULT_DEALS_PAGE_PATH)

    sent_channels = dispatch_notifications(config, deals, dry_run=args.dry_run)
    if deals and sent_channels > 0:
        analyzer.mark_deals_notified(deals)

    analyzer.save_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
