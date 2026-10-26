from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Iterable, List, Set

from src.models import EvaluatedDeal, FlightOffer

logger = logging.getLogger(__name__)

DEFAULT_ACTIVE_DEALS_PATH = Path(__file__).resolve().parent.parent / "data" / "active_deals.json"
DEFAULT_DEAL_EXCLUSIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "deal_exclusions.json"
DEAL_SIGNATURE_PATTERN = re.compile(
    r"^[A-Z]{3}-[A-Z]{3}:\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$"
)


def load_active_deals(path: Path = DEFAULT_ACTIVE_DEALS_PATH) -> List[EvaluatedDeal]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not isinstance(payload.get("deals"), list):
        raise ValueError(f"Ungültiges Format für aktive Deals: {path}")

    deals = []
    for index, item in enumerate(payload["deals"]):
        try:
            offer = FlightOffer(**item["offer"])
            deals.append(
                EvaluatedDeal(
                    offer=offer,
                    threshold_eur=item["threshold_eur"],
                    historical_avg_eur=item.get("historical_avg_eur"),
                    discount_vs_avg_percent=item.get("discount_vs_avg_percent"),
                    discount_vs_threshold_percent=item["discount_vs_threshold_percent"],
                    deal_score=item["deal_score"],
                    reason=item["reason"],
                    exclude_url=item.get("exclude_url", ""),
                    extra_metadata=item.get("extra_metadata", {}),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Ungültiger aktiver Deal an Position {index} in {path}: {exc}") from exc
    return deals


def load_deal_exclusions(path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH) -> Set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not isinstance(payload.get("excluded_signatures"), list):
        raise ValueError(f"Ungültiges Format für Deal-Ausschlüsse: {path}")
    signatures = payload["excluded_signatures"]
    if any(not isinstance(signature, str) or not DEAL_SIGNATURE_PATTERN.fullmatch(signature) for signature in signatures):
        raise ValueError(f"Ungültige Deal-Signatur in {path}")
    return set(signatures)


def save_json_atomic(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temp_path = Path(file.name)
            json.dump(payload, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def save_active_deals(deals: List[EvaluatedDeal], path: Path = DEFAULT_ACTIVE_DEALS_PATH) -> None:
    save_json_atomic({"deals": [deal_to_dict(deal) for deal in deals]}, path)


def save_deal_exclusions(
    signatures: Iterable[str],
    path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
) -> None:
    normalized = sorted(set(signatures))
    if any(not DEAL_SIGNATURE_PATTERN.fullmatch(signature) for signature in normalized):
        raise ValueError("Ungültige Deal-Signatur zum Ausschließen.")
    save_json_atomic({"excluded_signatures": normalized}, path)


def merge_active_deals(
    existing: Iterable[EvaluatedDeal],
    current: Iterable[EvaluatedDeal],
    excluded_signatures: Set[str],
    today: date | None = None,
) -> List[EvaluatedDeal]:
    today = today or date.today()
    merged = {deal.offer.deal_signature: deal for deal in existing}

    for deal in current:
        merged[deal.offer.deal_signature] = deal

    active = []
    for signature, deal in merged.items():
        if signature in excluded_signatures:
            continue
        try:
            departure = date.fromisoformat(deal.offer.outbound_date[:10])
        except ValueError as exc:
            raise ValueError(f"Ungültiges Abflugdatum für Deal {signature}: {exc}") from exc
        if departure < today:
            continue
        active.append(deal)

    active.sort(key=lambda deal: (-deal.deal_score, deal.offer.price_eur))
    return active


def deal_to_dict(deal: EvaluatedDeal) -> dict:
    return {
        "offer": {
            "origin": deal.offer.origin,
            "origin_name": deal.offer.origin_name,
            "destination": deal.offer.destination,
            "destination_name": deal.offer.destination_name,
            "destination_country": deal.offer.destination_country,
            "outbound_date": deal.offer.outbound_date,
            "inbound_date": deal.offer.inbound_date,
            "price_eur": deal.offer.price_eur,
            "airline": deal.offer.airline,
            "provider": deal.offer.provider,
            "stops": deal.offer.stops,
            "booking_url": deal.offer.booking_url,
            "is_wishlist": deal.offer.is_wishlist,
            "verified_live": deal.offer.verified_live,
        },
        "threshold_eur": deal.threshold_eur,
        "historical_avg_eur": deal.historical_avg_eur,
        "discount_vs_avg_percent": deal.discount_vs_avg_percent,
        "discount_vs_threshold_percent": deal.discount_vs_threshold_percent,
        "deal_score": deal.deal_score,
        "reason": deal.reason,
        "exclude_url": deal.exclude_url,
        "extra_metadata": deal.extra_metadata,
    }
