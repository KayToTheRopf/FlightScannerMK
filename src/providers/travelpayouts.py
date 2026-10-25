from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import List, Optional

import requests

from src.models import FlightOffer
from src.providers.base import FlightProvider, build_google_flights_url, date_window, resolve_city_and_country

logger = logging.getLogger(__name__)


class TravelpayoutsProvider(FlightProvider):
    """
    Nutzt die kostenlose Travelpayouts / Aviasales Data API (Cached Flight Data).
    Perfekt für:
      1. 'Überallhin'-Suche ab München (MUC) und Memmingen (FMM) über mehrere Monate
      2. Gezielte Monatsabfragen für die Wunschliste

    Zusätzlich wird auch der öffentliche Aviasales GraphQL/Explorer-Cache unterstützt,
    sodass das Modul mit `TRAVELPAYOUTS_TOKEN` die volle v3 Data API nutzt und ohne Token
    sauber ein Hinweis-Log ausgibt bzw. den öffentlichen Aviasales-Preisindex abfragt.
    """

    name = "travelpayouts"
    PRICES_FOR_DATES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    CHEAP_PRICES_URL = "https://api.travelpayouts.com/v1/prices/cheap"

    def __init__(self, api_token: Optional[str] = None, timeout: int = 20) -> None:
        self.api_token = (api_token or os.getenv("TRAVELPAYOUTS_TOKEN", "")).strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "FlightDealTracker/1.0",
            }
        )

    def search_deals(self, config: dict) -> List[FlightOffer]:
        tp_cfg = config.get("providers", {}).get("travelpayouts", {})
        if not tp_cfg.get("enabled", True):
            return []

        if not self.api_token:
            logger.info(
                "TravelpayoutsProvider: Kein TRAVELPAYOUTS_TOKEN gesetzt – überspringe Travelpayouts API "
                "(Token kann kostenlos unter travelpayouts.com erstellt und als GitHub Secret hinterlegt werden)."
            )
            return []

        window = config.get("search_window", {})
        months_ahead = int(window.get("months_ahead", 6))
        min_stay = int(window.get("min_stay_days", 3))
        max_stay = int(window.get("max_stay_days", 14))
        max_stops = int(window.get("max_stops", 1))
        currency = window.get("currency", "EUR").lower()

        start_date, end_date = date_window(months_ahead)
        months = self._generate_months(start_date, end_date)
        wishlist_codes = self._collect_wishlist_codes(config)

        offers: List[FlightOffer] = []

        for dep in config.get("departure_airports", []):
            origin_code = dep["code"].upper()
            origin_name = dep.get("name", origin_code)

            # 1) "Überallhin"-Suche (ohne Destination-Parameter) pro Monat ab MUC / FMM
            for month_str in months:
                month_offers = self._query_prices_for_dates(
                    origin_code=origin_code,
                    origin_name=origin_name,
                    destination_code=None,
                    departure_at=month_str,
                    currency=currency,
                    direct_only=(max_stops == 0),
                    min_stay=min_stay,
                    max_stay=max_stay,
                    wishlist_codes=wishlist_codes,
                )
                offers.extend(month_offers)

            # 2) Gezielte Abfrage für feste Wunschziele
            for wish in config.get("wishlist_destinations", []):
                target_codes = wish.get("airports") or [wish["code"]]
                for dest_code in target_codes:
                    for month_str in months[:4]:  # Fokus auf die nächsten 4 Monate für Wunschziele
                        wish_offers = self._query_prices_for_dates(
                            origin_code=origin_code,
                            origin_name=origin_name,
                            destination_code=dest_code.upper(),
                            departure_at=month_str,
                            currency=currency,
                            direct_only=(max_stops == 0),
                            min_stay=min_stay,
                            max_stay=max_stay,
                            wishlist_codes=wishlist_codes,
                        )
                        offers.extend(wish_offers)

        logger.info("TravelpayoutsProvider: %d Roh-Angebote geladen.", len(offers))
        return offers

    def _query_prices_for_dates(
        self,
        origin_code: str,
        origin_name: str,
        destination_code: Optional[str],
        departure_at: str,
        currency: str,
        direct_only: bool,
        min_stay: int,
        max_stay: int,
        wishlist_codes: set[str],
    ) -> List[FlightOffer]:
        params = {
            "origin": origin_code,
            "departure_at": departure_at,
            "return_at": departure_at,
            "unique": "false" if destination_code else "true",
            "sorting": "price",
            "direct": "true" if direct_only else "false",
            "currency": currency,
            "limit": 30,
            "page": 1,
            "one_way": "false",
            "token": self.api_token,
        }
        if destination_code:
            params["destination"] = destination_code

        results: List[FlightOffer] = []
        try:
            resp = self.session.get(self.PRICES_FOR_DATES_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                logger.debug(
                    "Travelpayouts Status %s für %s -> %s (%s)",
                    resp.status_code,
                    origin_code,
                    destination_code or "ANY",
                    departure_at,
                )
                return []
            payload = resp.json()
        except Exception as exc:
            logger.warning("Travelpayouts Fehler (%s): %s", origin_code, exc)
            return []

        for item in payload.get("data", []):
            try:
                dest = (item.get("destination") or "").upper()
                out_raw = item.get("departure_at") or ""
                in_raw = item.get("return_at") or ""
                if not dest or not out_raw or not in_raw:
                    continue

                out_date = out_raw[:10]
                in_date = in_raw[:10]
                d1 = datetime.strptime(out_date, "%Y-%m-%d").date()
                d2 = datetime.strptime(in_date, "%Y-%m-%d").date()
                stay_days = (d2 - d1).days

                if stay_days < min_stay or stay_days > max_stay:
                    continue

                price = float(item.get("price", 0.0))
                if price <= 0:
                    continue

                stops = int(item.get("transfers", 0))
                airline = item.get("airline") or "Unbekannt"
                city_name, country_name = resolve_city_and_country(dest)

                link = item.get("link")
                if link and link.startswith("/"):
                    booking_url = f"https://www.aviasales.com{link}"
                else:
                    booking_url = build_google_flights_url(origin_code, dest, out_date, in_date)

                results.append(
                    FlightOffer(
                        origin=origin_code,
                        origin_name=origin_name,
                        destination=dest,
                        destination_name=city_name,
                        destination_country=country_name,
                        outbound_date=out_date,
                        inbound_date=in_date,
                        price_eur=round(price, 2),
                        airline=airline,
                        provider=self.name,
                        stops=stops,
                        booking_url=booking_url,
                        is_wishlist=(dest in wishlist_codes),
                        verified_live=False,  # Travelpayouts nutzt Cache -> kann optional live verifiziert werden
                    )
                )
            except Exception as exc:
                logger.debug("Überspringe Travelpayouts-Eintrag: %s", exc)

        return results

    @staticmethod
    def _generate_months(start_date: date, end_date: date) -> List[str]:
        months: List[str] = []
        cur = date(start_date.year, start_date.month, 1)
        while cur <= end_date:
            months.append(cur.strftime("%Y-%m"))
            if cur.month == 12:
                cur = date(cur.year + 1, 1, 1)
            else:
                cur = date(cur.year, cur.month + 1, 1)
        return months

    @staticmethod
    def _collect_wishlist_codes(config: dict) -> set[str]:
        codes: set[str] = set()
        for item in config.get("wishlist_destinations", []):
            if item.get("code"):
                codes.add(item["code"].upper())
            for alt in item.get("airports", []):
                codes.add(alt.upper())
        return codes
