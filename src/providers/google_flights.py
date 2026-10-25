from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from src.models import FlightOffer
from src.providers.base import FlightProvider, build_google_flights_url, date_window, resolve_city_and_country

logger = logging.getLogger(__name__)


class GoogleFlightsProvider(FlightProvider):
    """
    Nutzt `fast-flights` (Google Flights Engine ohne API-Key, 100 % kostenlos),
    um:
      1. Feste Wunschziele ab München (MUC) und Memmingen (FMM) gezielt zu prüfen
      2. Gecachte Schnäppchen aus Travelpayouts live zu verifizieren
    """

    name = "google_flights"

    def search_deals(self, config: dict) -> List[FlightOffer]:
        gf_cfg = config.get("providers", {}).get("google_flights", {})
        if not gf_cfg.get("enabled", True):
            return []

        window = config.get("search_window", {})
        months_ahead = int(window.get("months_ahead", 6))
        min_stay = int(window.get("min_stay_days", 3))
        max_stay = int(window.get("max_stay_days", 14))
        max_stops = int(window.get("max_stops", 1))
        sample_count = int(gf_cfg.get("sample_dates_per_wishlist", 2))

        start_date, end_date = date_window(months_ahead)
        date_pairs = self._generate_rotating_date_pairs(start_date, end_date, min_stay, max_stay, sample_count)

        offers: List[FlightOffer] = []
        departures = config.get("departure_airports", [])
        wishlists = config.get("wishlist_destinations", [])

        for dep in departures:
            origin_code = dep["code"].upper()
            origin_name = dep.get("name", origin_code)

            for wish in wishlists:
                target_codes = wish.get("airports") or [wish["code"]]
                wish_city = wish.get("name", "")
                wish_country = wish.get("country", "")

                for dest_code in target_codes:
                    dest_code = dest_code.upper()
                    for out_date, in_date in date_pairs:
                        offer = self.query_single_roundtrip(
                            origin_code=origin_code,
                            origin_name=origin_name,
                            dest_code=dest_code,
                            outbound_date=out_date,
                            inbound_date=in_date,
                            max_stops=max_stops,
                            fallback_city=wish_city,
                            fallback_country=wish_country,
                            is_wishlist=True,
                        )
                        if offer is not None:
                            offers.append(offer)

        logger.info("GoogleFlightsProvider: %d Live-Angebote für Wunschziele geladen.", len(offers))
        return offers

    def verify_cached_offer(self, offer: FlightOffer, max_stops: int = 1) -> Optional[FlightOffer]:
        """Prüft ein gecachtes Angebot (z.B. von Travelpayouts) live über Google Flights."""
        live_offer = self.query_single_roundtrip(
            origin_code=offer.origin,
            origin_name=offer.origin_name,
            dest_code=offer.destination,
            outbound_date=offer.outbound_date,
            inbound_date=offer.inbound_date,
            max_stops=max_stops,
            fallback_city=offer.destination_name,
            fallback_country=offer.destination_country,
            is_wishlist=offer.is_wishlist,
        )
        return live_offer

    def query_single_roundtrip(
        self,
        origin_code: str,
        origin_name: str,
        dest_code: str,
        outbound_date: str,
        inbound_date: str,
        max_stops: int = 1,
        fallback_city: str = "",
        fallback_country: str = "",
        is_wishlist: bool = False,
    ) -> Optional[FlightOffer]:
        """Fragt den günstigsten Hin- und Rückflug via `fast_flights` ab (inkl. EU-Cookie-Consent-Bypass)."""
        try:
            import fast_flights.core as ffc
            from fast_flights import FlightData, Passengers, create_filter
            from primp import Client
        except ImportError:
            logger.warning("Paket 'fast-flights' nicht installiert – überspringe Google Flights Live-Abfrage.")
            return None

        try:
            # EU-Consent-Cookies setzen, damit Google Flights in Europa keine Cookie-Wall statt Flügen liefert
            client = Client(impersonate="chrome_126", verify=False)
            eu_cookies = {
                "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiAo_CmBg",
                "CONSENT": "PENDING+987",
            }
            ffc.fetch = lambda params: client.get(
                "https://www.google.com/travel/flights",
                params=params,
                cookies=eu_cookies,
            )

            max_stops_arg = 0 if max_stops == 0 else 1
            filter_obj = create_filter(
                flight_data=[
                    FlightData(date=outbound_date, from_airport=origin_code, to_airport=dest_code),
                    FlightData(date=inbound_date, from_airport=dest_code, to_airport=origin_code),
                ],
                trip="round-trip",
                seat="economy",
                passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
                max_stops=max_stops_arg,
            )
            result = ffc.get_flights_from_filter(filter_obj, currency="EUR", mode="common")
            if not result or not getattr(result, "flights", None):
                return None

            best_price: Optional[float] = None
            best_airline: str = "Google Flights"
            best_stops: int = 0

            for fl in result.flights:
                parsed_price = self._parse_price_eur(getattr(fl, "price", ""))
                if parsed_price is None or parsed_price <= 0:
                    continue
                stops_val = getattr(fl, "stops", 0)
                stops_int = int(stops_val) if isinstance(stops_val, int) else 0
                if stops_int > max_stops:
                    continue
                if best_price is None or parsed_price < best_price:
                    best_price = parsed_price
                    best_airline = getattr(fl, "name", None) or "Airline"
                    best_stops = stops_int

            if best_price is None:
                return None

            city_name, country_name = resolve_city_and_country(dest_code, fallback_city, fallback_country)
            return FlightOffer(
                origin=origin_code,
                origin_name=origin_name,
                destination=dest_code,
                destination_name=city_name,
                destination_country=country_name,
                outbound_date=outbound_date,
                inbound_date=inbound_date,
                price_eur=round(best_price, 2),
                airline=best_airline,
                provider=self.name,
                stops=best_stops,
                booking_url=build_google_flights_url(origin_code, dest_code, outbound_date, inbound_date),
                is_wishlist=is_wishlist,
                verified_live=True,
            )
        except Exception as exc:
            logger.debug(
                "GoogleFlights Abfrage für %s->%s (%s bis %s) fehlgeschlagen: %s",
                origin_code,
                dest_code,
                outbound_date,
                inbound_date,
                exc,
            )
            return None

    @staticmethod
    def _parse_price_eur(raw_price: str) -> Optional[float]:
        if not raw_price:
            return None
        cleaned = re.sub(r"[^\d,.]", "", str(raw_price)).strip()
        if not cleaned:
            return None
        # Behandle deutsche (1.234,56) und englische (1,234.56) Zahlenformate
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts[-1]) == 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _generate_rotating_date_pairs(
        start_date: date,
        end_date: date,
        min_stay: int,
        max_stay: int,
        sample_count: int,
    ) -> List[Tuple[str, str]]:
        """
        Wählt pro Tag/Lauf rotierende Wochenend- und Wochentags-Fenster (z.B. 4 Tage Kurztrip, 7 Tage Urlaub)
        über die nächsten 6 Monate aus, damit bei jedem Lauf neue Zeiträume geprüft werden.
        """
        total_days = max(14, (end_date - start_date).days - max_stay)
        # Tages-Offset sorgt dafür, dass morgens und abends unterschiedliche Wochen geprüft werden
        day_of_year = datetime.utcnow().timetuple().tm_yday
        hour_slot = 0 if datetime.utcnow().hour < 12 else 1
        seed_offset = (day_of_year * 2 + hour_slot) * 7

        stay_options = [min(max(4, min_stay), max_stay), min(max(7, min_stay), max_stay), min(max(10, min_stay), max_stay)]
        pairs: List[Tuple[str, str]] = []

        for idx in range(sample_count):
            offset = (seed_offset + idx * (total_days // max(1, sample_count))) % total_days
            out_d = start_date + timedelta(days=offset)
            # Schiebe Abflug bevorzugt auf Donnerstag/Freitag/Samstag für attraktive Trips
            weekday_shift = (4 - out_d.weekday()) % 7
            out_d = out_d + timedelta(days=weekday_shift)
            stay = stay_options[idx % len(stay_options)]
            in_d = out_d + timedelta(days=stay)
            if in_d <= end_date:
                pairs.append((out_d.isoformat(), in_d.isoformat()))

        return pairs
