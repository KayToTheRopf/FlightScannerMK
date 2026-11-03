from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlsplit

from src.active_deals import (
    DEFAULT_ACTIVE_DEALS_PATH,
    DEFAULT_DEAL_EXCLUSIONS_PATH,
    deal_to_dict,
    load_active_deals,
    load_deal_exclusions,
)
from src.analyzer import DealAnalyzer
from src.deal_page import render_deals_page, write_deals_page
from src.handle_feedback import (
    DEFAULT_BLACKLIST_PATH,
    DEFAULT_CONFIG_PATH,
    add_deal_exclusion,
    add_exclusion,
    add_or_update_wishlist,
    get_pause_until,
    load_blacklist,
    remove_deal_exclusion,
    remove_exclusion,
    remove_wishlist,
    set_radar_pause,
    trigger_test_discord,
)
from src.models import EvaluatedDeal
from src.run_search import DEFAULT_HISTORY_PATH, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_DEALS_PAGE_PATH = ROOT_DIR / "site" / "index.html"


def get_current_filtered_deals() -> List[EvaluatedDeal]:
    """Lädt aktive Flug-Deals und filtert ausgeschlossene Deals sowie Blacklist-Orte heraus."""
    deals = load_active_deals(DEFAULT_ACTIVE_DEALS_PATH)
    excluded_signatures = load_deal_exclusions(DEFAULT_DEAL_EXCLUSIONS_PATH)
    config = load_config(DEFAULT_CONFIG_PATH)
    analyzer = DealAnalyzer(
        config=config,
        blacklist_path=DEFAULT_BLACKLIST_PATH,
        history_path=DEFAULT_HISTORY_PATH,
    )

    filtered: List[EvaluatedDeal] = []
    for deal in deals:
        offer = deal.offer
        if offer.deal_signature in excluded_signatures:
            continue
        if analyzer.is_blacklisted(offer):
            continue
        filtered.append(deal)

    filtered.sort(key=lambda d: (-d.deal_score, d.offer.price_eur))
    return filtered


def get_last_updated_timestamp(path: Path = DEFAULT_ACTIVE_DEALS_PATH) -> datetime:
    candidate_paths = [
        path,
        DEFAULT_CONFIG_PATH,
        DEFAULT_BLACKLIST_PATH,
        DEFAULT_DEAL_EXCLUSIONS_PATH,
    ]
    mtimes = [p.stat().st_mtime for p in candidate_paths if p.exists()]
    if mtimes:
        return datetime.fromtimestamp(max(mtimes), tz=timezone.utc)
    return datetime.now(timezone.utc)


def build_current_deals_page_html() -> str:
    deals = get_current_filtered_deals()
    generated_at = get_last_updated_timestamp(DEFAULT_ACTIVE_DEALS_PATH)
    paused_until = get_pause_until(DEFAULT_CONFIG_PATH)
    blacklist = load_blacklist(DEFAULT_BLACKLIST_PATH)
    excluded_deals = load_deal_exclusions(DEFAULT_DEAL_EXCLUSIONS_PATH)
    config = load_config(DEFAULT_CONFIG_PATH)
    return render_deals_page(
        deals,
        generated_at=generated_at,
        paused_until=paused_until,
        blacklist=blacklist,
        excluded_deals=excluded_deals,
        wishlist_destinations=config.get("wishlist_destinations", []),
        departure_airports=config.get("departure_airports", []),
    )


def refresh_static_deals_page() -> None:
    try:
        deals = get_current_filtered_deals()
        paused_until = get_pause_until(DEFAULT_CONFIG_PATH)
        blacklist = load_blacklist(DEFAULT_BLACKLIST_PATH)
        excluded_deals = load_deal_exclusions(DEFAULT_DEAL_EXCLUSIONS_PATH)
        config = load_config(DEFAULT_CONFIG_PATH)
        write_deals_page(
            deals,
            DEFAULT_DEALS_PAGE_PATH,
            paused_until=paused_until,
            blacklist=blacklist,
            excluded_deals=excluded_deals,
            wishlist_destinations=config.get("wishlist_destinations", []),
            departure_airports=config.get("departure_airports", []),
        )
    except Exception as exc:
        logger.warning("Konnte statische Deal-Seite nicht aktualisieren: %s", exc)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class FlightRadarRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_bytes(
        self,
        status_code: int,
        content_type: str,
        body: bytes,
        head_only: bool = False,
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_json(self, status_code: int, payload: dict, head_only: bool = False) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(status_code, "application/json; charset=utf-8", body, head_only=head_only)

    def _send_html(self, status_code: int, html_text: str, head_only: bool = False) -> None:
        body = html_text.encode("utf-8")
        self._send_bytes(status_code, "text/html; charset=utf-8", body, head_only=head_only)

    def _handle_read(self, head_only: bool = False) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/api/health":
            self._send_json(200, {"status": "ok"}, head_only=head_only)
            return

        if path == "/api/deals":
            deals = get_current_filtered_deals()
            config = load_config(DEFAULT_CONFIG_PATH)
            blacklist = load_blacklist(DEFAULT_BLACKLIST_PATH)
            excluded_deals = sorted(load_deal_exclusions(DEFAULT_DEAL_EXCLUSIONS_PATH))
            paused_until = get_pause_until(DEFAULT_CONFIG_PATH)
            self._send_json(
                200,
                {
                    "count": len(deals),
                    "paused_until": paused_until,
                    "deals": [deal_to_dict(d) for d in deals],
                    "wishlist_destinations": config.get("wishlist_destinations", []),
                    "departure_airports": config.get("departure_airports", []),
                    "blacklist": blacklist,
                    "excluded_deals": excluded_deals,
                },
                head_only=head_only,
            )
            return

        if path in ("/", "/index.html"):
            html_content = build_current_deals_page_html()
            self._send_html(200, html_content, head_only=head_only)
            return

        self._send_json(404, {"error": "Not found"}, head_only=head_only)

    def do_HEAD(self) -> None:
        self._handle_read(head_only=True)

    def do_GET(self) -> None:
        self._handle_read(head_only=False)

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else ""

        data: dict = {}
        if raw_body:
            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError:
                form = parse_qs(raw_body)
                data = {k: v[0] for k, v in form.items() if v}

        if parsed.path == "/api/pause":
            target = str(data.get("target", "")).strip()
            changed, message = set_radar_pause(target, DEFAULT_CONFIG_PATH)
            paused_until = get_pause_until(DEFAULT_CONFIG_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(
                200 if changed else 400,
                {"changed": changed, "message": message, "paused_until": paused_until},
            )
            return

        if parsed.path == "/api/exclude-deal":
            signature = str(data.get("signature", "")).strip()
            changed, message = add_deal_exclusion(signature, DEFAULT_DEAL_EXCLUSIONS_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/unexclude-deal":
            signature = str(data.get("signature", "")).strip()
            changed, message = remove_deal_exclusion(signature, DEFAULT_DEAL_EXCLUSIONS_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/exclude":
            target = str(data.get("target", "")).strip()
            changed, message = add_exclusion(target, DEFAULT_BLACKLIST_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/unexclude":
            target = str(data.get("target", "")).strip()
            changed, message = remove_exclusion(target, DEFAULT_BLACKLIST_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/wishlist":
            code = str(data.get("code", "")).strip()
            name = str(data.get("name", "")).strip() or None
            try:
                max_price = float(data.get("max_price_eur", 100.0))
            except (TypeError, ValueError):
                self._send_json(400, {"changed": False, "message": "Ungültiger Maximalpreis."})
                return
            changed, message = add_or_update_wishlist(
                code=code,
                max_price_eur=max_price,
                name=name,
                config_path=DEFAULT_CONFIG_PATH,
            )
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/unwatch":
            code = str(data.get("code", "")).strip()
            changed, message = remove_wishlist(code=code, config_path=DEFAULT_CONFIG_PATH)
            if changed:
                refresh_static_deals_page()
            self._send_json(200 if changed else 400, {"changed": changed, "message": message})
            return

        if parsed.path == "/api/test-discord":
            changed, message = trigger_test_discord(
                config_path=DEFAULT_CONFIG_PATH,
                blacklist_path=DEFAULT_BLACKLIST_PATH,
                deal_exclusions_path=DEFAULT_DEAL_EXCLUSIONS_PATH,
            )
            if changed:
                refresh_static_deals_page()
            self._send_json(
                200 if changed else 400,
                {
                    "changed": changed,
                    "message": message,
                    "has_webhook": bool(os.getenv("DISCORD_WEBHOOK_URL", "").strip()),
                },
            )
            return

        self._send_json(404, {"error": "Not found"})


def main() -> None:
    refresh_static_deals_page()

    port = int(os.environ.get("PORT", "3000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = ReusableThreadingHTTPServer((host, port), FlightRadarRequestHandler)
    logger.info("Flug-Schnäppchen-Radar Server läuft auf http://%s:%d", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
