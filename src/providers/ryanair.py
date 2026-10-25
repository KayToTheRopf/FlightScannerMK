from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List

import requests

from src.models import FlightOffer
from src.providers.base import FlightProvider, build_google_flights_url, date_window, resolve_city_and_country

logger = logging.getLogger(__name__)


class RyanairProvider(FlightProvider):
    """
    Nutzt die öffentliche, kostenlose Ryanair FareFinder API (ohne API-Key!).
    Besonders stark für Memmingen (FMM) sowie Low-Cost-Routen im Umland.
    Fragt in einem einzigen Call die günstigsten Hin- und Rückflüge ('Überallhin')
    für die gewünschte Aufenthaltsdauer (z.B. 3-14 Tage) ab.
    """

    name = "ryanair"
    BASE_URL = "https://www.ryanair.com/api/farfnd/v4/roundTripFares"

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )

    def search_deals(self, config: dict) -> List[FlightOffer]:
        if not config.get("providers", {}).get("ryanair", {}).get("enabled", True):
            return []

        window = config.get("search_window", {})
        months_ahead = int(window.get("months_ahead", 6))
        min_stay = int(window.get("min_stay_days", 3))
        max_stay = int(window.get("max_stay_days", 14))
        currency = window.get("currency", "EUR")

        wishlist_codes = self._collect_wishlist_codes(config)
        wishlist_limits = self._collect_wishlist_limits(config)

        start_date, end_date = date_window(months_ahead)
        offers: List[FlightOffer] = []

        for dep in config.get("departure_airports", []):
            origin_code = dep["code"].upper()
            origin_name = dep.get("name", origin_code)
            # Wir holen bis zum höchsten relevanten Preis (entweder Explore-Max oder höchster Wunschlisten-Preis)
            max_explore = float(dep.get("max_explore_price_eur", 100.0))
            max_wishlist = max(wishlist_limits.values(), default=max_explore)
            price_ceiling = int(max(max_explore, max_wishlist) * 1.35)

            # Da derSuchhorizont 6 Monate beträgt, teilen wir die Abfrage in 2 Monatsblöcke (je 3 Monate),
            # damit nicht nur der allererste günstige Monat zurückgegeben wird, sondern Vielfalt entsteht.
            chunk_days = 90
            chunk_start = start_date
            while chunk_start < end_date:
                chunk_end = min(end_date, chunk_start + timedelta(days=chunk_days))
                chunk_offers = self._fetch_roundtrip_fares(
                    origin_code=origin_code,
                    origin_name=origin_name,
                    outbound_from=chunk_start,
                    outbound_to=chunk_end,
                    min_stay=min_stay,
                    max_stay=max_stay,
                    currency=currency,
                    price_ceiling=price_ceiling,
                    wishlist_codes=wishlist_codes,
                )
                offers.extend(chunk_offers)
                chunk_start = chunk_end + timedelta(days=1)

        logger.info("RyanairProvider: %d Roh-Angebote geladen.", len(offers))
        return offers

    def _fetch_roundtrip_fares(
        self,
        origin_code: str,
        origin_name: str,
        outbound_from: date,
        outbound_to: date,
        min_stay: int,
        max_stay: int,
        currency: str,
        price_ceiling: int,
        wishlist_codes: set[str],
    ) -> List[FlightOffer]:
        inbound_to = outbound_to + timedelta(days=max_stay)
        params = {
            "departureAirportIataCode": origin_code,
            "outboundDepartureDateFrom": outbound_from.isoformat(),
            "outboundDepartureDateTo": outbound_to.isoformat(),
            "inboundDepartureDateFrom": (outbound_from + timedelta(days=min_stay)).isoformat(),
            "inboundDepartureDateTo": inbound_to.isoformat(),
            "durationFrom": min_stay,
            "durationTo": max_stay,
            "market": "de-de",
            "adultPaxCount": 1,
            "priceValueTo": price_ceiling,
            "currency": currency,
            "searchMode": "ALL",
        }

        results: List[FlightOffer] = []
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(
                    "Ryanair API antwortete mit Status %s für %s", resp.status_code, origin_code
                )
                return []
            data = resp.json()
        except Exception as exc:
            logger.warning("Fehler bei Ryanair-Abfrage ab %s: %s", origin_code, exc)
            return []

        for fare in data.get("fares", []):
            try:
                outbound = fare.get("outbound", {})
                inbound = fare.get("inbound", {})
                summary = fare.get("summary", {})
                price_info = summary.get("price", {})

                total_price = float(price_info.get("value", 0.0))
                if total_price <= 0:
                    continue

                arr_airport = outbound.get("arrivalAirport", {})
                dest_code = (arr_airport.get("iataCode") or "").upper()
                if not dest_code:
                    continue

                api_city = arr_airport.get("city", {}).get("name") or arr_airport.get("name", "")
                api_country = arr_airport.get("countryName", "")
                dest_city, dest_country = resolve_city_and_country(dest_code, api_city, api_country)

                out_date = (outbound.get("departureDate") or "")[:10]
                in_date = (inbound.get("departureDate") or "")[:10]
                if not out_date or not in_date:
                    continue

                booking_url = (
                    f"https://www.ryanair.com/de/de/trip/flights/select"
                    f"?adults=1&teens=0&children=0&infants=0"
                    f"&dateOut={out_date}&dateIn={in_date}"
                    f"&isConnectedFlight=false&discount=0&isReturn=true"
                    f"&originIata={origin_code}&destinationIata={dest_code}"
                )

                offer = FlightOffer(
                    origin=origin_code,
                    origin_name=origin_name,
                    destination=dest_code,
                    destination_name=dest_city,
                    destination_country=dest_country,
                    outbound_date=out_date,
                    inbound_date=in_date,
                    price_eur=round(total_price, 2),
                    airline="Ryanair",
                    provider=self.name,
                    stops=0,
                    booking_url=booking_url or build_google_flights_url(origin_code, dest_code, out_date, in_date),
                    is_wishlist=(dest_code in wishlist_codes),
                    verified_live=True,
                )
                results.append(offer)
            except Exception as exc:
                logger.debug("Überspringe fehlerhaften Ryanair-Datensatz: %s", exc)

        return results

    @staticmethod
    def _collect_wishlist_codes(config: dict) -> set[str]:
        codes: set[str] = set()
        for item in config.get("wishlist_destinations", []):
            if item.get("code"):
                codes.add(item["code"].upper())
            for alt in item.get("airports", []):
                codes.add(alt.upper())
        return codes

    @staticmethod
    def _collect_wishlist_limits(config: dict) -> dict[str, float]:
        limits: dict[str, float] = {}
        for item in config.get("wishlist_destinations", []):
            max_p = float(item.get("max_price_eur", 100.0))
            if item.get("code"):
                limits[item["code"].upper()] = max_p
            for alt in item.get("airports", []):
                limits[alt.upper()] = max_p
        return limits
