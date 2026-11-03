from __future__ import annotations

import html
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable, List
from urllib.parse import quote, urlsplit, urlunsplit

from src.active_deals import DEFAULT_DEAL_EXCLUSIONS_PATH, load_deal_exclusions
from src.compat import yaml_mod as yaml
from src.handle_feedback import DEFAULT_BLACKLIST_PATH, DEFAULT_CONFIG_PATH, load_blacklist
from src.models import EvaluatedDeal
from src.providers.base import resolve_city_and_country

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


def _get_repo_slug(repo_slug: str = "") -> str:
    slug = (repo_slug or os.getenv("GITHUB_REPOSITORY", "") or "KayToTheRopf/FlightScannerMK").strip()
    if "/" not in slug:
        slug = "KayToTheRopf/FlightScannerMK"
    return slug


def _build_pause_issue_url(target: str, repo_slug: str = "") -> str:
    slug = _get_repo_slug(repo_slug)
    if target == "off":
        title = quote("resume:now")
        body = quote(
            "Bitte den Flug-Schnäppchen-Radar sofort wieder aktivieren (`/resume`).\n\n"
            "*(Einfach auf 'Submit new issue' klicken.)*"
        )
    else:
        title = quote(f"pause:{target}")
        body = quote(
            f"Bitte den Flug-Schnäppchen-Radar für `{target}` pausieren.\n\n"
            "*(Einfach auf 'Submit new issue' klicken.)*"
        )
    return f"https://github.com/{slug}/issues/new?title={title}&labels=feedback-exclude&body={body}"


def _build_feedback_issue_url(title_raw: str, body_raw: str, repo_slug: str = "") -> str:
    slug = _get_repo_slug(repo_slug)
    return (
        f"https://github.com/{slug}/issues/new?title={quote(title_raw)}"
        f"&labels=feedback-exclude&body={quote(body_raw)}"
    )


def _format_deal_signature(sig: str) -> str:
    parts = sig.split(":")
    if len(parts) == 3 and "-" in parts[0]:
        origin, dest = parts[0].split("-", 1)
        city_name, _ = resolve_city_and_country(dest)
        dest_label = f"{dest} ({city_name})" if city_name and city_name.upper() != dest.upper() else dest
        return f"{origin} → {dest_label} · {parts[1]} bis {parts[2]} ({sig})"
    return sig


def _load_default_config_lists() -> tuple[List[dict], List[dict]]:
    if not DEFAULT_CONFIG_PATH.exists():
        return [], []
    try:
        with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("wishlist_destinations", []) or [], cfg.get("departure_airports", []) or []
    except Exception:
        return [], []


def render_deals_page(
    deals: List[EvaluatedDeal],
    generated_at: datetime | None = None,
    paused_until: str | None = None,
    repo_slug: str = "",
    blacklist: dict | None = None,
    excluded_deals: Iterable[str] | None = None,
    wishlist_destinations: List[dict] | None = None,
    departure_airports: List[dict] | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    timestamp_utc = generated_at.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    try:
        berlin_dt = generated_at.astimezone(ZoneInfo("Europe/Berlin"))
        timestamp_de = f"{berlin_dt.strftime('%d.%m.%Y %H:%M')} Uhr"
    except Exception:
        timestamp_de = timestamp_utc

    if blacklist is None:
        try:
            blacklist = load_blacklist(DEFAULT_BLACKLIST_PATH)
        except Exception:
            blacklist = {"excluded_airports": [], "excluded_cities": [], "excluded_countries": []}

    if excluded_deals is None:
        try:
            excluded_deals_list = sorted(load_deal_exclusions(DEFAULT_DEAL_EXCLUSIONS_PATH))
        except Exception:
            excluded_deals_list = []
    else:
        excluded_deals_list = sorted(set(excluded_deals))

    if wishlist_destinations is None or departure_airports is None:
        default_wishlist, default_departures = _load_default_config_lists()
        if wishlist_destinations is None:
            wishlist_destinations = default_wishlist
        if departure_airports is None:
            departure_airports = default_departures

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

    url_3d = html.escape(_build_pause_issue_url("3d", repo_slug), quote=True)
    url_7d = html.escape(_build_pause_issue_url("7d", repo_slug), quote=True)
    url_14d = html.escape(_build_pause_issue_url("14d", repo_slug), quote=True)
    url_30d = html.escape(_build_pause_issue_url("30d", repo_slug), quote=True)
    url_resume = html.escape(_build_pause_issue_url("off", repo_slug), quote=True)
    url_test_discord = html.escape(
        _build_feedback_issue_url(
            "test-discord",
            "Bitte sofort eine Test-Discord-Nachricht mit den aktuellen Top-Schnäppchen senden (`/test-discord`).\n\n*(Einfach auf 'Submit new issue' klicken.)*",
            repo_slug,
        ),
        quote=True,
    )
    slug_escaped = html.escape(_get_repo_slug(repo_slug), quote=True)

    if paused_until:
        status_badge = f'<span class="status-pill status-paused">⏸ Pausiert bis einschl. {html.escape(paused_until)}</span>'
        pause_notice = (
            f'<p class="pause-note">Automatische Suchläufe und Benachrichtigungen sind bis einschließlich '
            f'<strong>{html.escape(paused_until)}</strong> ausgesetzt.</p>'
        )
        resume_btn = (
            f'<a class="button button-resume" href="{url_resume}" '
            f'onclick="return setRadarPause(\'off\', this.href)">▶ Radar jetzt fortsetzen</a>'
        )
    else:
        status_badge = '<span class="status-pill status-active">🟢 Radar aktiv (2x täglich)</span>'
        pause_notice = '<p class="pause-note">Du kannst die automatische Flugsuche und Benachrichtigungen für einen Zeitraum pausieren:</p>'
        resume_btn = ""

    # Blacklist & Deal-Exclusions Chips bauen
    ex_airports: List[str] = [str(a).strip() for a in (blacklist.get("excluded_airports") or []) if str(a).strip()]
    ex_cities: List[str] = [str(c).strip() for c in (blacklist.get("excluded_cities") or []) if str(c).strip()]
    ex_countries: List[str] = [str(co).strip() for co in (blacklist.get("excluded_countries") or []) if str(co).strip()]
    ex_airlines: List[str] = [str(al).strip() for al in (blacklist.get("excluded_airlines") or []) if str(al).strip()]

    airport_chips = []
    for code in ex_airports:
        city_name, _ = resolve_city_and_country(code.upper())
        label = f"{code.upper()} ({city_name})" if city_name and city_name.upper() != code.upper() else code.upper()
        un_url = html.escape(
            _build_feedback_issue_url(
                f"unexclude:{code.upper()}",
                f"Bitte Flughafen `{code.upper()}` wieder von der Blacklist entfernen.",
                repo_slug,
            ),
            quote=True,
        )
        code_js = html.escape(code.upper(), quote=True)
        airport_chips.append(
            f'<span class="chip chip-exclusion">🛫 {html.escape(label)} '
            f'<a class="chip-remove" href="{un_url}" title="Von Blacklist entfernen" '
            f'onclick="return removeExclusion(\'{code_js}\', this.href)">×</a></span>'
        )

    city_chips = []
    for city in ex_cities:
        un_url = html.escape(
            _build_feedback_issue_url(
                f"unexclude:{city}",
                f"Bitte Stadt/Ort `{city}` wieder von der Blacklist entfernen.",
                repo_slug,
            ),
            quote=True,
        )
        city_js = html.escape(city, quote=True)
        city_chips.append(
            f'<span class="chip chip-exclusion">🏙️ {html.escape(city)} '
            f'<a class="chip-remove" href="{un_url}" title="Von Blacklist entfernen" '
            f'onclick="return removeExclusion(\'{city_js}\', this.href)">×</a></span>'
        )

    country_chips = []
    for country in ex_countries:
        un_url = html.escape(
            _build_feedback_issue_url(
                f"unexclude:{country}",
                f"Bitte Land `{country}` wieder von der Blacklist entfernen.",
                repo_slug,
            ),
            quote=True,
        )
        country_js = html.escape(country, quote=True)
        country_chips.append(
            f'<span class="chip chip-exclusion">🌍 {html.escape(country)} '
            f'<a class="chip-remove" href="{un_url}" title="Von Blacklist entfernen" '
            f'onclick="return removeExclusion(\'{country_js}\', this.href)">×</a></span>'
        )

    airline_chips = [
        f'<span class="chip chip-exclusion">✈️ {html.escape(airline)}</span>'
        for airline in ex_airlines
    ]

    deal_exclusion_chips = []
    for sig in excluded_deals_list:
        formatted_sig = _format_deal_signature(sig)
        un_deal_url = html.escape(
            _build_feedback_issue_url(
                f"unexclude-deal:{sig}",
                f"Bitte den Deal-Ausschluss `{sig}` wieder aufheben.",
                repo_slug,
            ),
            quote=True,
        )
        sig_js = html.escape(sig, quote=True)
        deal_exclusion_chips.append(
            f'<span class="chip chip-deal-exclusion">🎫 {html.escape(formatted_sig)} '
            f'<a class="chip-remove" href="{un_deal_url}" title="Deal-Ausschluss aufheben" '
            f'onclick="return removeDealExclusion(\'{sig_js}\', this.href)">×</a></span>'
        )

    total_exclusions = (
        len(ex_airports) + len(ex_cities) + len(ex_countries) + len(ex_airlines) + len(excluded_deals_list)
    )

    airports_html = (
        "".join(airport_chips)
        if airport_chips
        else '<span class="muted-empty">Keine Flughäfen ausgeschlossen</span>'
    )
    cities_html = (
        "".join(city_chips)
        if city_chips
        else '<span class="muted-empty">Keine Städte ausgeschlossen</span>'
    )
    countries_html = (
        "".join(country_chips)
        if country_chips
        else '<span class="muted-empty">Keine Länder ausgeschlossen</span>'
    )
    deals_ex_html = (
        "".join(deal_exclusion_chips)
        if deal_exclusion_chips
        else '<span class="muted-empty">Keine einzelnen Deals ausgeschlossen</span>'
    )
    airlines_row_html = (
        f'<div class="exclusion-group"><span class="group-label">Ausgeschlossene Airlines:</span>'
        f'<div class="chip-list">{"".join(airline_chips)}</div></div>'
        if airline_chips
        else ""
    )

    # Überwachte Abflughäfen & Wunschziele bauen
    dep_chips = []
    for dep in departure_airports or []:
        d_code = str(dep.get("code", "")).strip()
        d_name = str(dep.get("name", d_code)).strip()
        d_max = dep.get("max_explore_price_eur")
        limit_str = f" · Explore ≤ {float(d_max):.0f} €" if d_max is not None else ""
        if d_code:
            dep_chips.append(
                f'<span class="chip chip-departure">🛫 {html.escape(d_name)} ({html.escape(d_code)}){html.escape(limit_str)}</span>'
            )

    wish_chips = []
    for w in wishlist_destinations or []:
        w_code = str(w.get("code", "")).strip()
        w_name = str(w.get("name", w_code)).strip()
        w_country = str(w.get("country", "")).strip()
        w_max = w.get("max_price_eur")
        limit_str = f" ≤ {float(w_max):.0f} €" if w_max is not None else ""
        country_str = f", {w_country}" if w_country else ""
        if w_code:
            unwatch_url = html.escape(
                _build_feedback_issue_url(
                    f"unwatch:{w_code.upper()}",
                    f"Bitte Wunschziel `{w_code.upper()}` ({w_name}) aus der Wunschliste entfernen.",
                    repo_slug,
                ),
                quote=True,
            )
            w_code_js = html.escape(w_code.upper(), quote=True)
            w_name_js = html.escape(w_name, quote=True)
            w_price_js = f"{float(w_max):.0f}" if w_max is not None else "100"
            wish_chips.append(
                f'<span class="chip chip-wishlist">'
                f'<span class="chip-edit-trigger" title="Klicken, um Preisgrenze anzupassen" '
                f'onclick="fillWishlistForm(\'{w_code_js}\', \'{w_price_js}\', \'{w_name_js}\')">'
                f'⭐ {html.escape(w_name)} ({html.escape(w_code)}{html.escape(country_str)}){html.escape(limit_str)}'
                f'</span> '
                f'<a class="chip-remove chip-remove-wish" href="{unwatch_url}" title="Wunschziel entfernen" '
                f'onclick="return removeWishlist(\'{w_code_js}\', this.href)">×</a></span>'
            )

    dep_html = "".join(dep_chips) if dep_chips else '<span class="muted-empty">Standard (MUC, FMM)</span>'
    wish_html = "".join(wish_chips) if wish_chips else '<span class="muted-empty">Keine festen Wunschziele konfiguriert</span>'
    wish_count = len(wish_chips)

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
    .pause-panel, .config-panel {{ margin-bottom: 1.25rem; padding: 1rem 1.25rem; background: white; border: 1px solid #dce3ee; border-radius: 12px; box-shadow: 0 3px 12px #172b4d0b; }}
    .pause-panel.is-paused {{ background: #fffbeb; border-color: #f59e0b; }}
    .pause-header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: .75rem; }}
    .pause-title {{ font-weight: 700; font-size: 1rem; margin: 0; }}
    .status-pill {{ display: inline-block; padding: .25rem .65rem; border-radius: 999px; font-size: .85rem; font-weight: 650; }}
    .status-active {{ background: #dcfce7; color: #166534; }}
    .status-paused {{ background: #fef3c7; color: #92400e; }}
    .status-count {{ background: #fee2e2; color: #991b1b; }}
    .pause-note {{ margin: .5rem 0 .75rem; color: #475467; font-size: .92rem; }}
    .pause-controls {{ display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }}
    .pause-date-group {{ display: inline-flex; align-items: center; gap: .4rem; flex-wrap: wrap; }}
    .pause-date-input, .text-input {{ padding: .45rem .6rem; border: 1px solid #cbd5e1; border-radius: 7px; font-size: .88rem; color: #172033; background: white; }}
    .pause-feedback {{ margin-top: .6rem; font-size: .88rem; font-weight: 600; color: #174ea6; display: none; }}
    .exclusion-grid {{ display: grid; gap: .75rem; margin-top: .75rem; }}
    .exclusion-group {{ display: grid; grid-template-columns: 210px 1fr; align-items: start; gap: .5rem; padding-bottom: .5rem; border-bottom: 1px dashed #e2e8f0; }}
    .exclusion-group:last-of-type {{ border-bottom: none; padding-bottom: 0; }}
    .group-label {{ font-size: .88rem; font-weight: 650; color: #334155; padding-top: .2rem; }}
    .chip-list {{ display: flex; flex-wrap: wrap; gap: .45rem; align-items: center; }}
    .chip {{ display: inline-flex; align-items: center; gap: .35rem; padding: .28rem .65rem; border-radius: 999px; font-size: .84rem; font-weight: 600; }}
    .chip-exclusion {{ background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}
    .chip-deal-exclusion {{ background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }}
    .chip-wishlist {{ background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }}
    .chip-departure {{ background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }}
    .chip-edit-trigger {{ cursor: pointer; }}
    .chip-edit-trigger:hover {{ text-decoration: underline; }}
    .chip-remove {{ display: inline-flex; align-items: center; justify-content: center; width: 1.15rem; height: 1.15rem; border-radius: 999px; background: #fee2e2; color: #7f1d1d; text-decoration: none; font-weight: 700; font-size: .85rem; line-height: 1; }}
    .chip-remove:hover {{ background: #fca5a5; }}
    .chip-remove-wish {{ background: #dbeafe; color: #1e3a8a; }}
    .chip-remove-wish:hover {{ background: #93c5fd; }}
    .status-wish {{ background: #dbeafe; color: #1e40af; }}
    .input-code {{ width: 9.5rem; text-transform: uppercase; }}
    .input-price {{ width: 9.5rem; }}
    .muted-empty {{ color: #64748b; font-size: .86rem; font-style: italic; padding-top: .15rem; }}
    .inline-form {{ margin-top: .85rem; padding-top: .75rem; border-top: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }}
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
    .button {{ display: inline-block; padding: .65rem .9rem; border-radius: 7px; color: white; text-decoration: none; font-weight: 650; border: none; cursor: pointer; font-size: .9rem; }}
    .button-sm {{ padding: .45rem .75rem; font-size: .85rem; }}
    .button-book {{ background: #1769aa; }} .button-exclude {{ background: #b42318; }}
    .button-pause {{ background: #475467; }} .button-resume {{ background: #15803d; }}
    .button-discord {{ background: #5865F2; }}
    .button-disabled {{ background: #697586; cursor: default; }}
    .empty {{ padding: 2rem; background: white; border-radius: 12px; text-align: center; }}
    footer {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #586579; font-size: .85rem; }}
    @media (max-width: 640px) {{
      dl div {{ grid-template-columns: 1fr; gap: .15rem; }}
      .exclusion-group {{ grid-template-columns: 1fr; gap: .25rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>✈ Flug-Schnäppchen-Radar</h1>
    <p>{html.escape(summary)}</p>
    <p>Letzte Aktualisierung: <span id="last-updated-time" data-utc="{html.escape(timestamp_utc)}" title="{html.escape(timestamp_utc)}">{html.escape(timestamp_de)}</span></p>
  </header>
  <main>
    <section class="pause-panel{' is-paused' if paused_until else ''}" aria-label="Radar-Steuerung">
      <div class="pause-header">
        <p class="pause-title">⏱ Radar-Status &amp; Pause-Steuerung</p>
        {status_badge}
      </div>
      {pause_notice}
      <div class="pause-controls">
        {resume_btn}
        <a class="button button-sm button-pause" href="{url_3d}" onclick="return setRadarPause('3d', this.href)">⏸ 3 Tage</a>
        <a class="button button-sm button-pause" href="{url_7d}" onclick="return setRadarPause('7d', this.href)">⏸ 7 Tage</a>
        <a class="button button-sm button-pause" href="{url_14d}" onclick="return setRadarPause('14d', this.href)">⏸ 14 Tage</a>
        <a class="button button-sm button-pause" href="{url_30d}" onclick="return setRadarPause('30d', this.href)">⏸ 30 Tage</a>
        <span class="pause-date-group">
          <input type="date" id="pause-until-date" class="pause-date-input" value="{html.escape(paused_until or '')}" aria-label="Pausieren bis Datum">
          <button type="button" class="button button-sm button-pause" onclick="setRadarPauseFromDate()">Bis Datum pausieren</button>
        </span>
        <a class="button button-sm button-discord" href="{url_test_discord}" onclick="return sendTestDiscord(this.href)">🔔 Test-Discord senden</a>
      </div>
      <div id="pause-feedback" class="pause-feedback"></div>
    </section>

    <section class="config-panel" aria-label="Ausgeschlossene Ziele und Deals">
      <div class="pause-header">
        <p class="pause-title">🚫 Ausgeschlossene Ziele &amp; Deals (Blacklist)</p>
        <span class="status-pill status-count">{total_exclusions} Ausschlüsse aktiv</span>
      </div>
      <p class="pause-note">Diese Flughäfen, Städte, Länder und einzelnen Verbindungen werden bei der Schnäppchen-Suche ignoriert:</p>
      <div class="exclusion-grid">
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Flughäfen:</span>
          <div class="chip-list">{airports_html}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Städte / Orte:</span>
          <div class="chip-list">{cities_html}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Länder:</span>
          <div class="chip-list">{countries_html}</div>
        </div>
        {airlines_row_html}
        <div class="exclusion-group">
          <span class="group-label">Ausgeschlossene Einzel-Deals:</span>
          <div class="chip-list">{deals_ex_html}</div>
        </div>
      </div>
      <div class="inline-form">
        <input type="text" id="exclude-target-input" class="text-input" placeholder="IATA (z.B. TIA), Stadt oder country:Land" aria-label="Ziel ausschließen">
        <button type="button" class="button button-sm button-exclude" onclick="addExclusionFromInput()">🚫 Ziel ausschließen</button>
      </div>
      <div id="exclude-feedback" class="pause-feedback"></div>
    </section>

    <section class="config-panel" aria-label="Überwachte Abflughäfen und Wunschziele">
      <div class="pause-header">
        <p class="pause-title">🎯 Überwachte Abflughäfen &amp; Wunschziele</p>
        <span class="status-pill status-wish">{wish_count} Wunschziele aktiv</span>
      </div>
      <p class="pause-note">Klicke auf ein Wunschziel, um dessen Maximalpreis anzupassen, oder füge unten ein neues Reiseziel per 3-Buchstaben-IATA-Code hinzu:</p>
      <div class="exclusion-grid">
        <div class="exclusion-group">
          <span class="group-label">Abflughäfen (Explore-Limit):</span>
          <div class="chip-list">{dep_html}</div>
        </div>
        <div class="exclusion-group">
          <span class="group-label">Wunschziele (Maximalpreis):</span>
          <div class="chip-list">{wish_html}</div>
        </div>
      </div>
      <div class="inline-form">
        <input type="text" id="wishlist-code-input" class="text-input input-code" maxlength="3" placeholder="IATA (z.B. LIS)" aria-label="Wunschziel IATA-Code">
        <input type="number" id="wishlist-price-input" class="text-input input-price" min="1" step="1" placeholder="Max. € (z.B. 110)" aria-label="Maximalpreis in Euro">
        <input type="text" id="wishlist-name-input" class="text-input" placeholder="Städtename (optional, z.B. Lissabon)" aria-label="Optionaler Städtename">
        <button type="button" class="button button-sm button-book" onclick="saveWishlistFromInput()">⭐ Wunschziel speichern</button>
      </div>
      <div id="wishlist-feedback" class="pause-feedback"></div>
    </section>

    <section class="deal-list" aria-label="Gefundene Flugangebote">{content}</section>
  </main>
  <footer>Preise und Verfügbarkeiten können sich jederzeit ändern. Bitte beim Anbieter prüfen.</footer>
  <script>
    const REPO_SLUG = "{slug_escaped}";
    function setRadarPause(target, fallbackUrl) {{
      const fb = document.getElementById("pause-feedback");
      if (fb) {{
        fb.style.display = "block";
        fb.textContent = "Speichere Einstellung...";
      }}
      fetch("/api/pause", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ target: target }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        if (fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }});
      return false;
    }}
    function setRadarPauseFromDate() {{
      const input = document.getElementById("pause-until-date");
      const val = input ? input.value.trim() : "";
      if (!val) return;
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent("pause:" + val) + "&labels=feedback-exclude";
      setRadarPause(val, issueUrl);
    }}
    function addExclusionFromInput() {{
      const input = document.getElementById("exclude-target-input");
      const val = input ? input.value.trim() : "";
      if (!val) return;
      const fb = document.getElementById("exclude-feedback");
      if (fb) {{
        fb.style.display = "block";
        fb.textContent = "Speichere Ausschluss...";
      }}
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent("exclude:" + val) + "&labels=feedback-exclude";
      fetch("/api/exclude", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ target: val }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        window.open(issueUrl, "_blank", "noopener,noreferrer");
      }});
    }}
    function removeExclusion(target, fallbackUrl) {{
      fetch("/api/unexclude", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ target: target }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        if (fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }});
      return false;
    }}
    function removeDealExclusion(signature, fallbackUrl) {{
      fetch("/api/unexclude-deal", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ signature: signature }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        if (fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }});
      return false;
    }}
    function fillWishlistForm(code, price, name) {{
      const codeInput = document.getElementById("wishlist-code-input");
      const priceInput = document.getElementById("wishlist-price-input");
      const nameInput = document.getElementById("wishlist-name-input");
      if (codeInput) codeInput.value = code || "";
      if (priceInput) priceInput.value = price || "";
      if (nameInput) nameInput.value = name || "";
      if (priceInput) priceInput.focus();
    }}
    function saveWishlistFromInput() {{
      const codeInput = document.getElementById("wishlist-code-input");
      const priceInput = document.getElementById("wishlist-price-input");
      const nameInput = document.getElementById("wishlist-name-input");
      const code = codeInput ? codeInput.value.trim().toUpperCase() : "";
      const priceRaw = priceInput ? priceInput.value.trim() : "";
      const name = nameInput ? nameInput.value.trim() : "";
      const fb = document.getElementById("wishlist-feedback");
      if (!/^[A-Z]{{3}}$/.test(code)) {{
        if (fb) {{
          fb.style.display = "block";
          fb.textContent = "Bitte einen gültigen 3-stelligen IATA-Flughafencode eingeben (z.B. LIS, PMI, ATH).";
        }}
        return;
      }}
      const price = parseFloat(priceRaw.replace(",", "."));
      if (!price || price <= 0) {{
        if (fb) {{
          fb.style.display = "block";
          fb.textContent = "Bitte einen gültigen Maximalpreis in Euro eingeben (z.B. 110).";
        }}
        return;
      }}
      if (fb) {{
        fb.style.display = "block";
        fb.textContent = "Speichere Wunschziel...";
      }}
      const titleRaw = name ? ("watch:" + code + ":" + Math.round(price) + ":" + name) : ("watch:" + code + ":" + Math.round(price));
      const issueUrl = "https://github.com/" + REPO_SLUG + "/issues/new?title=" + encodeURIComponent(titleRaw) + "&labels=feedback-exclude";
      fetch("/api/wishlist", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ code: code, max_price_eur: price, name: name || null }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        window.open(issueUrl, "_blank", "noopener,noreferrer");
      }});
    }}
    function removeWishlist(code, fallbackUrl) {{
      fetch("/api/unwatch", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ code: code }})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function() {{
        window.location.reload();
      }})
      .catch(function() {{
        if (fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }});
      return false;
    }}
    function sendTestDiscord(fallbackUrl) {{
      const fb = document.getElementById("pause-feedback");
      if (fb) {{
        fb.style.display = "block";
        fb.textContent = "Sende / aktiviere Test-Discord...";
      }}
      fetch("/api/test-discord", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{}})
      }})
      .then(function(res) {{
        if (!res.ok) throw new Error("Static hosting fallback");
        return res.json();
      }})
      .then(function(data) {{
        if (fb) {{
          fb.style.display = "block";
          fb.textContent = data.message || "Test-Discord wurde vorgemerkt!";
        }}
        if (!data.has_webhook && fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }})
      .catch(function() {{
        if (fallbackUrl) {{
          window.open(fallbackUrl, "_blank", "noopener,noreferrer");
        }}
      }});
      return false;
    }}
  </script>
</body>
</html>
"""


def write_deals_page(
    deals: List[EvaluatedDeal],
    path: Path,
    paused_until: str | None = None,
    repo_slug: str = "",
    blacklist: dict | None = None,
    excluded_deals: Iterable[str] | None = None,
    wishlist_destinations: List[dict] | None = None,
    departure_airports: List[dict] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_deals_page(
            deals,
            paused_until=paused_until,
            repo_slug=repo_slug,
            blacklist=blacklist,
            excluded_deals=excluded_deals,
            wishlist_destinations=wishlist_destinations,
            departure_airports=departure_airports,
        ),
        encoding="utf-8",
    )
    logger.info("Deal-Seite mit %d Angebot(en) geschrieben: %s", len(deals), path)


