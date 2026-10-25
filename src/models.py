from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FlightOffer:
    """Standardisiertes Hin- und Rückflug-Angebot eines Providers."""

    origin: str
    origin_name: str
    destination: str
    destination_name: str
    destination_country: str
    outbound_date: str  # YYYY-MM-DD
    inbound_date: str   # YYYY-MM-DD
    price_eur: float
    airline: str
    provider: str       # z.B. "ryanair", "travelpayouts", "google_flights"
    stops: int = 0
    booking_url: str = ""
    is_wishlist: bool = False
    verified_live: bool = True

    @property
    def stay_days(self) -> int:
        try:
            d1 = datetime.strptime(self.outbound_date[:10], "%Y-%m-%d").date()
            d2 = datetime.strptime(self.inbound_date[:10], "%Y-%m-%d").date()
            return (d2 - d1).days
        except ValueError:
            return 0

    @property
    def route_key(self) -> str:
        return f"{self.origin.upper()}-{self.destination.upper()}"

    @property
    def deal_signature(self) -> str:
        """Eindeutiger Schlüssel für Cooldown/Deduplizierung (Route + Reisedaten)."""
        return f"{self.route_key}:{self.outbound_date[:10]}:{self.inbound_date[:10]}"


@dataclass
class EvaluatedDeal:
    """Ein als echtes Schnäppchen eingestuftes Flugangebot inkl. Preisvergleich."""

    offer: FlightOffer
    threshold_eur: float
    historical_avg_eur: Optional[float]
    discount_vs_avg_percent: Optional[float]
    discount_vs_threshold_percent: float
    deal_score: float
    reason: str
    exclude_url: str = ""
    extra_metadata: dict = field(default_factory=dict)
