from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from src.models import EvaluatedDeal, FlightOffer

logger = logging.getLogger(__name__)


def build_exclude_issue_url(repo: str, destination_code: str, destination_name: str, country: str = "") -> str:
    """
    Erzeugt einen 1-Klick-GitHub-Issue-Link.
    Klickt der Nutzer in Discord/Mail/GitHub darauf und bestätigt mit 'Submit new issue',
    wird der Ort durch den Workflow `feedback_handler.yml` automatisch in `blacklist.json` eingetragen.
    """
    if not repo:
        repo = os.getenv("GITHUB_REPOSITORY", "DEIN-USER/flight-deal-tracker")
    title = f"exclude:{destination_code.upper()}"
    body = (
        f"Bitte dieses Reiseziel künftig von der Flugpreis-Suche ausschließen:\n\n"
        f"- **IATA-Code:** `{destination_code.upper()}`\n"
        f"- **Stadt:** {destination_name}\n"
        f"- **Land:** {country}\n\n"
        f"*(Einfach auf 'Submit new issue' klicken – die GitHub Action trägt den Ort automatisch in `config/blacklist.json` ein und schließt dieses Ticket.)*"
    )
    return (
        f"https://github.com/{repo}/issues/new"
        f"?title={quote(title)}&labels={quote('feedback-exclude')}&body={quote(body)}"
    )


class DealAnalyzer:
    """
    Prüft gefundene Flugangebote gegen:
      1. Blacklist (`config/blacklist.json`)
      2. Reisedauer (3-14 Tage) & Stopp-Limits
      3. Zielpreis-Schwellen (Wunschliste vs. Überallhin-Explore)
      4. Historische Durchschnittspreise (`data/price_history.json`) -> Echte Schnäppchen!
      5. Cooldown bereits gemeldeter Deals (keine doppelten Benachrichtigungen)
    """

    def __init__(
        self,
        config: dict,
        blacklist_path: Path,
        history_path: Path,
        repo_slug: str = "",
    ) -> None:
        self.config = config
        self.blacklist_path = blacklist_path
        self.history_path = history_path
        self.repo_slug = repo_slug or os.getenv("GITHUB_REPOSITORY", "")
        self.blacklist = self._load_json(
            blacklist_path,
            default={"excluded_airports": [], "excluded_cities": [], "excluded_countries": []},
        )
        self.history = self._load_json(
            history_path,
            default={"routes": {}, "notified_deals": {}, "last_run_utc": None},
        )

    @staticmethod
    def _load_json(path: Path, default: dict) -> dict:
        if not path.exists():
            return dict(default)
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Konnte JSON %s nicht laden (%s) – nutze Standardwerte.", path, exc)
            return dict(default)

    def save_history(self) -> None:
        self.history["last_run_utc"] = datetime.now(timezone.utc).isoformat()
        self._cleanup_expired_notifications()
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def is_blacklisted(self, offer: FlightOffer) -> bool:
        airports = {a.upper().strip() for a in self.blacklist.get("excluded_airports", [])}
        cities = {c.lower().strip() for c in self.blacklist.get("excluded_cities", [])}
        countries = {c.lower().strip() for c in self.blacklist.get("excluded_countries", [])}

        if offer.destination.upper() in airports:
            return True
        if offer.destination_name.lower().strip() in cities:
            return True
        if offer.destination_country.lower().strip() in countries:
            return True
        return False

    def evaluate_offers(self, offers: List[FlightOffer]) -> List[EvaluatedDeal]:
        window = self.config.get("search_window", {})
        min_stay = int(window.get("min_stay_days", 3))
        max_stay = int(window.get("max_stay_days", 14))
        max_stops = int(window.get("max_stops", 1))

        scoring_cfg = self.config.get("deal_scoring", {})
        min_hist_discount = float(scoring_cfg.get("min_discount_vs_history_percent", 25.0))
        first_seen_margin = float(scoring_cfg.get("first_seen_margin_percent", 10.0))
        cooldown_days = int(scoring_cfg.get("notification_cooldown_days", 7))
        max_deals = int(scoring_cfg.get("max_deals_per_run", 10))

        origin_thresholds = self._origin_explore_thresholds()
        wishlist_thresholds = self._wishlist_thresholds()

        # 1. Dedupliziere identische Routen+Datums-Angebote (behalte günstigsten Preis)
        best_by_signature: Dict[str, FlightOffer] = {}
        for offer in offers:
            if self.is_blacklisted(offer):
                continue
            if offer.stay_days < min_stay or offer.stay_days > max_stay:
                continue
            if offer.stops > max_stops:
                continue
            sig = offer.deal_signature
            if sig not in best_by_signature or offer.price_eur < best_by_signature[sig].price_eur:
                best_by_signature[sig] = offer

        # 2. Aktualisiere Routen-Statistik & bewerte Schnäppchen
        deals: List[EvaluatedDeal] = []
        for offer in best_by_signature.values():
            threshold = self._get_threshold_for_offer(offer, origin_thresholds, wishlist_thresholds)
            hist_avg, obs_count = self._get_route_history(offer.route_key)

            # Aktualisiere gleitende Preishistorie für diese Route
            self._record_route_observation(offer.route_key, offer.price_eur, offer.destination_name)

            # Preis muss unter der konfigurierten Maximalgrenze liegen
            if offer.price_eur > threshold:
                continue

            discount_vs_threshold = round(((threshold - offer.price_eur) / threshold) * 100.0, 1)
            discount_vs_avg: Optional[float] = None
            is_true_bargain = False
            reason = ""

            if hist_avg is not None and obs_count >= 2 and hist_avg > 0:
                discount_vs_avg = round(((hist_avg - offer.price_eur) / hist_avg) * 100.0, 1)
                if discount_vs_avg >= min_hist_discount:
                    is_true_bargain = True
                    reason = f"{discount_vs_avg:.0f}% unter Ø-Routenpreis ({hist_avg:.0f} €)"
                elif discount_vs_threshold >= 25.0:
                    is_true_bargain = True
                    reason = f"{discount_vs_threshold:.0f}% unter Zielpreis ({threshold:.0f} €)"
            else:
                # Noch keine ausreichende Historie für diese Route -> prüfe Sicherheitsmarge unter Schwellenwert
                if discount_vs_threshold >= first_seen_margin:
                    is_true_bargain = True
                    reason = f"{discount_vs_threshold:.0f}% unter Preisgrenze ({threshold:.0f} €)"

            if not is_true_bargain:
                continue

            if self._is_on_cooldown(offer, cooldown_days):
                logger.debug("Deal %s übersprungen (bereits innerhalb der letzten %d Tage gemeldet).", offer.deal_signature, cooldown_days)
                continue

            # Berechne Gesamt-Score (Wunschziele erhalten Bonus, hohe prozentuale Ersparnis zählt stark)
            base_score = discount_vs_avg if (discount_vs_avg is not None and discount_vs_avg > 0) else discount_vs_threshold
            wishlist_bonus = 15.0 if offer.is_wishlist else 0.0
            direct_bonus = 5.0 if offer.stops == 0 else 0.0
            deal_score = round(base_score + wishlist_bonus + direct_bonus, 2)

            exclude_url = build_exclude_issue_url(
                repo=self.repo_slug,
                destination_code=offer.destination,
                destination_name=offer.destination_name,
                country=offer.destination_country,
            )

            deals.append(
                EvaluatedDeal(
                    offer=offer,
                    threshold_eur=threshold,
                    historical_avg_eur=round(hist_avg, 2) if hist_avg else None,
                    discount_vs_avg_percent=discount_vs_avg,
                    discount_vs_threshold_percent=discount_vs_threshold,
                    deal_score=deal_score,
                    reason=reason,
                    exclude_url=exclude_url,
                )
            )

        # Sortiere nach bestem Deal-Score (und bei Gleichstand nach niedrigstem Preis)
        deals.sort(key=lambda d: (-d.deal_score, d.offer.price_eur))

        # Behalte pro Zielort (Origin -> Destination) max. die 2 besten Termine, damit die Liste abwechslungsreich bleibt
        diversified: List[EvaluatedDeal] = []
        per_route_count: Dict[str, int] = {}
        for d in deals:
            rk = d.offer.route_key
            if per_route_count.get(rk, 0) >= 2:
                continue
            per_route_count[rk] = per_route_count.get(rk, 0) + 1
            diversified.append(d)
            if len(diversified) >= max_deals:
                break

        return diversified

    def mark_deals_notified(self, deals: List[EvaluatedDeal]) -> None:
        notified = self.history.setdefault("notified_deals", {})
        now_iso = datetime.now(timezone.utc).isoformat()
        for d in deals:
            notified[d.offer.deal_signature] = {
                "price_eur": d.offer.price_eur,
                "notified_at_utc": now_iso,
                "destination": d.offer.destination,
                "destination_name": d.offer.destination_name,
            }

    def _origin_explore_thresholds(self) -> Dict[str, float]:
        res: Dict[str, float] = {}
        for dep in self.config.get("departure_airports", []):
            res[dep["code"].upper()] = float(dep.get("max_explore_price_eur", 100.0))
        return res

    def _wishlist_thresholds(self) -> Dict[str, float]:
        res: Dict[str, float] = {}
        for wish in self.config.get("wishlist_destinations", []):
            max_p = float(wish.get("max_price_eur", 100.0))
            if wish.get("code"):
                res[wish["code"].upper()] = max_p
            for alt in wish.get("airports", []):
                res[alt.upper()] = max_p
        return res

    @staticmethod
    def _get_threshold_for_offer(
        offer: FlightOffer,
        origin_thresholds: Dict[str, float],
        wishlist_thresholds: Dict[str, float],
    ) -> float:
        dest = offer.destination.upper()
        if dest in wishlist_thresholds:
            offer.is_wishlist = True
            return wishlist_thresholds[dest]
        return origin_thresholds.get(offer.origin.upper(), 100.0)

    def _get_route_history(self, route_key: str) -> Tuple[Optional[float], int]:
        routes = self.history.get("routes", {})
        entry = routes.get(route_key)
        if not entry:
            return None, 0
        return float(entry.get("avg_price_eur", 0.0)), int(entry.get("observations", 0))

    def _record_route_observation(self, route_key: str, price_eur: float, dest_name: str) -> None:
        routes = self.history.setdefault("routes", {})
        entry = routes.get(route_key)
        now_iso = datetime.now(timezone.utc).isoformat()
        if not entry:
            routes[route_key] = {
                "destination_name": dest_name,
                "avg_price_eur": round(price_eur, 2),
                "min_price_eur": round(price_eur, 2),
                "max_price_eur": round(price_eur, 2),
                "observations": 1,
                "last_seen_utc": now_iso,
            }
        else:
            obs = int(entry.get("observations", 1))
            old_avg = float(entry.get("avg_price_eur", price_eur))
            # Exponentiell gewichteter gleitender Durchschnitt (max. Gewicht 20 Beobachtungen)
            weight = min(obs, 20)
            new_avg = ((old_avg * weight) + price_eur) / (weight + 1)
            entry["avg_price_eur"] = round(new_avg, 2)
            entry["min_price_eur"] = round(min(float(entry.get("min_price_eur", price_eur)), price_eur), 2)
            entry["max_price_eur"] = round(max(float(entry.get("max_price_eur", price_eur)), price_eur), 2)
            entry["observations"] = obs + 1
            entry["last_seen_utc"] = now_iso

    def _is_on_cooldown(self, offer: FlightOffer, cooldown_days: int) -> bool:
        notified = self.history.get("notified_deals", {})
        prev = notified.get(offer.deal_signature)
        if not prev:
            return False
        try:
            prev_time = datetime.fromisoformat(prev["notified_at_utc"])
            if prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - prev_time
            if age > timedelta(days=cooldown_days):
                return False
            # Falls der Preis seit der letzten Meldung nochmal um mind. 15% gefallen ist, trotzdem melden!
            prev_price = float(prev.get("price_eur", offer.price_eur))
            if offer.price_eur <= prev_price * 0.85:
                return False
            return True
        except Exception:
            return False

    def _cleanup_expired_notifications(self, retention_days: int = 30) -> None:
        notified = self.history.get("notified_deals", {})
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        to_delete = []
        for sig, info in notified.items():
            try:
                ts = datetime.fromisoformat(info.get("notified_at_utc", ""))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    to_delete.append(sig)
            except Exception:
                to_delete.append(sig)
        for sig in to_delete:
            notified.pop(sig, None)
