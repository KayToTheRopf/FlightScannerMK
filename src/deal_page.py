from __future__ import annotations

import html
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import quote, urlsplit, urlunsplit

from src.models import EvaluatedDeal

logger = logging.getLogger(__name__)


def get_deals_page_url(repository: str = "", configured_url: str = "") -> str:
    """Return the configured Pages URL or derive the standard GitHub Pages URL."""
    configured_url = configured_url.strip()
    if configured_url:
        parsed = urlsplit(configured_url)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))
        logger.warning("FLIGHT_DEALS_PAGE_URL muss eine HTTPS-URL sein.")
        return ""

    repository = (repository or os.getenv("GITHUB_REPOSITORY", "")).strip()
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts):
        return ""

    owner, repo = (quote(part, safe="") for part in parts)
    base_url = f"https://{owner}.github.io"
    if repo.lower() == f"{owner}.github.io".lower():
        return f"{base_url}/"
    return f"{base_url}/{repo}/"


def _safe_link(url: str) -> str:
    parsed = urlsplit(url)
    return url if parsed.scheme == "https" and parsed.netloc else ""


def _button(label: str, url: str, style_class: str) -> str:
    safe_url = _safe_link(url)
    if not safe_url:
        return f'<span class="button button-disabled">{html.escape(label)}</span>'
    return (
        f'<a class="button {style_class}" href="{html.escape(safe_url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'
    )


def render_deals_page(deals: List[EvaluatedDeal], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    timestamp = generated_at.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    cards = []
    for deal in deals:
        offer = deal.offer
        badge = "Wunschziel" if offer.is_wishlist else "Explore-Deal"
        stops = "Direktflug" if offer.stops == 0 else f"{offer.stops} Stopp(s)"
        cards.append(
            f"""
            <article class="deal-card">
              <div class="deal-heading">
                <span class="badge">{html.escape(badge)}</span>
                <span class="price">{offer.price_eur:.2f} €</span>
              </div>
              <h2>{html.escape(offer.origin_name)} ({html.escape(offer.origin)}) → {html.escape(offer.destination_name)} ({html.escape(offer.destination)})</h2>
              <p class="country">{html.escape(offer.destination_country)}</p>
              <dl>
                <div><dt>Reisezeitraum</dt><dd>{html.escape(offer.outbound_date)} bis {html.escape(offer.inbound_date)} ({offer.stay_days} Tage)</dd></div>
                <div><dt>Airline</dt><dd>{html.escape(offer.airline)} · {html.escape(stops)} · {html.escape(offer.provider)}</dd></div>
                <div><dt>Ersparnis</dt><dd>{html.escape(deal.reason)}</dd></div>
              </dl>
              <div class="actions">
                {_button("✈ Flug ansehen & buchen", offer.booking_url, "button-book")}
                {_button("🚫 Diesen Deal ausschließen", deal.exclude_url, "button-exclude")}
              </div>
            </article>
            """
        )

    content = "\n".join(cards) if cards else (
        '<p class="empty">Aktuell sind keine aktiven Schnäppchen gespeichert.</p>'
    )
    best_price = min((deal.offer.price_eur for deal in deals), default=None)
    summary = f"{len(deals)} Schnäppchen gefunden"
    if best_price is not None:
        summary += f" · günstigster Flug ab {best_price:.2f} €"

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Aktuelle Flug-Schnäppchen ab München und Memmingen.">
  <title>Flug-Schnäppchen-Radar</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #172033; background: #f3f6fb; }}
    body {{ margin: 0; }}
    header {{ padding: 2rem max(1rem, calc((100% - 960px) / 2)); color: white; background: #172b4d; }}
    header h1 {{ margin: 0 0 .5rem; }}
    header p {{ margin: .25rem 0; }}
    main {{ max-width: 960px; margin: 1.5rem auto; padding: 0 1rem; }}
    .deal-list {{ display: grid; gap: 1rem; }}
    .deal-card {{ padding: 1.25rem; background: white; border: 1px solid #dce3ee; border-radius: 12px; box-shadow: 0 3px 12px #172b4d0b; }}
    .deal-heading {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; }}
    .badge {{ padding: .25rem .6rem; border-radius: 999px; background: #e8f1ff; color: #174ea6; font-size: .85rem; }}
    .price {{ color: #16803c; font-size: 1.4rem; font-weight: 700; white-space: nowrap; }}
    h2 {{ margin: 1rem 0 0; font-size: 1.25rem; }}
    .country {{ margin: .2rem 0 1rem; color: #586579; }}
    dl {{ display: grid; gap: .6rem; margin: 0 0 1rem; }}
    dl div {{ display: grid; grid-template-columns: 130px 1fr; gap: .5rem; }}
    dt {{ color: #586579; }} dd {{ margin: 0; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: .6rem; }}
    .button {{ display: inline-block; padding: .65rem .9rem; border-radius: 7px; color: white; text-decoration: none; font-weight: 650; }}
    .button-book {{ background: #1769aa; }} .button-exclude {{ background: #b42318; }}
    .button-disabled {{ background: #697586; }}
    .empty {{ padding: 2rem; background: white; border-radius: 12px; text-align: center; }}
    footer {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #586579; font-size: .85rem; }}
    @media (max-width: 560px) {{ dl div {{ grid-template-columns: 1fr; gap: .15rem; }} }}
  </style>
</head>
<body>
  <header>
    <h1>✈ Flug-Schnäppchen-Radar</h1>
    <p>{html.escape(summary)}</p>
    <p>Letzte Aktualisierung: {html.escape(timestamp)}</p>
  </header>
  <main><section class="deal-list" aria-label="Gefundene Flugangebote">{content}</section></main>
  <footer>Preise und Verfügbarkeiten können sich jederzeit ändern. Bitte beim Anbieter prüfen.</footer>
</body>
</html>
"""


def write_deals_page(deals: List[EvaluatedDeal], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_deals_page(deals), encoding="utf-8")
    logger.info("Deal-Seite mit %d Angebot(en) geschrieben: %s", len(deals), path)
