from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from src.compat import requests_mod as requests, yaml_mod as yaml

from src.active_deals import (
    DEFAULT_DEAL_EXCLUSIONS_PATH,
    DEAL_SIGNATURE_PATTERN,
    load_deal_exclusions,
    save_deal_exclusions,
)
from src.providers.base import resolve_city_and_country

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "search_config.yaml"
DEFAULT_BLACKLIST_PATH = ROOT_DIR / "config" / "blacklist.json"

logger = logging.getLogger(__name__)


def load_blacklist(path: Path = DEFAULT_BLACKLIST_PATH) -> dict:
    if not path.exists():
        return {"excluded_airports": [], "excluded_cities": [], "excluded_countries": []}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_blacklist(data: dict, path: Path = DEFAULT_BLACKLIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_pause_until(
    config_path: Path = DEFAULT_CONFIG_PATH,
    today: Optional[date] = None,
) -> Optional[str]:
    """
    Prüft, ob in `config/search_config.yaml` ein aktives `pause_until`-Datum gesetzt ist.
    Gibt das ISO-Datum (`YYYY-MM-DD`) zurück, falls die Pause noch aktiv ist (`pause_until >= today`),
    andernfalls `None`.
    """
    if not config_path.exists():
        return None
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return None

    raw_val = cfg.get("pause_until")
    if not raw_val:
        return None

    val_str = str(raw_val).strip()
    if not val_str:
        return None

    try:
        pause_date = date.fromisoformat(val_str[:10])
    except ValueError:
        return None

    ref_today = today or date.today()
    if pause_date >= ref_today:
        return pause_date.isoformat()
    return None


def set_radar_pause(
    target: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    today: Optional[date] = None,
) -> Tuple[bool, str]:
    """
    Pausiert den Flug-Radar für eine bestimmte Dauer oder bis zu einem Datum,
    oder hebt die Pause wieder auf.
    Unterstützt:
      - Tage/Wochen: `7`, `7d`, `7 Tage`, `14d`, `2w`, `2 Wochen`, `1m`
      - Datum: `2026-12-01` oder `01.12.2026`
      - Fortsetzen: `off`, `0`, `resume`, `weiter`, `unpause`, `start`, `false`, `stop`
    """
    raw = (target or "").strip()
    if not raw:
        return False, "Keine Pausendauer oder Ziel-Datum angegeben (z.B. `7d` oder `2026-12-01`)."

    ref_today = today or date.today()
    lower = raw.lower()

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # 1) Pause aufheben / Fortsetzen
    if lower in {"off", "0", "0d", "resume", "weiter", "unpause", "start", "false", "none", "stop", "active", "aktiv"}:
        cfg["pause_until"] = ""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
        return True, "▶️ **Flug-Schnäppchen-Radar ist wieder aktiv!** Die Pause wurde aufgehoben."

    target_date: Optional[date] = None

    # 2) ISO-Datum YYYY-MM-DD (optional mit "until " / "bis ")
    cleaned_date = re.sub(r"^(?:until|bis)\s+", "", raw, flags=re.IGNORECASE).strip()
    m_iso = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", cleaned_date)
    if m_iso:
        try:
            target_date = date.fromisoformat(m_iso.group(1))
        except ValueError:
            return False, f"Ungültiges Datum: `{cleaned_date}`."

    # 3) Deutsches Datum DD.MM.YYYY
    if target_date is None:
        m_de = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", cleaned_date)
        if m_de:
            try:
                target_date = date(int(m_de.group(3)), int(m_de.group(2)), int(m_de.group(1)))
            except ValueError:
                return False, f"Ungültiges Datum: `{cleaned_date}`."

    # 4) Dauer in Tagen / Wochen / Monaten: z.B. "7", "7d", "14 Tage", "2w", "2 Wochen", "1m"
    if target_date is None:
        m_dur = re.fullmatch(
            r"(\d+)\s*(d|day|days|t|tag|tage|w|week|weeks|woche|wochen|m|month|months|monat|monate)?",
            lower,
        )
        if m_dur:
            amount = int(m_dur.group(1))
            unit = (m_dur.group(2) or "d").lower()
            if amount <= 0:
                cfg["pause_until"] = ""
                with config_path.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
                return True, "▶️ **Flug-Schnäppchen-Radar ist wieder aktiv!** Die Pause wurde aufgehoben."
            if unit.startswith("w"):
                days = amount * 7
            elif unit.startswith("m"):
                days = amount * 30
            else:
                days = amount
            days = min(days, 365)
            target_date = ref_today + timedelta(days=days)

    if target_date is None:
        return (
            False,
            f"Ungültige Pausen-Angabe `{raw}`. Beispiele: `/pause 7d`, `/pause 2w`, `/pause 2026-12-01` oder `/resume`.",
        )

    if target_date < ref_today:
        return False, f"Das angegebene Datum `{target_date.isoformat()}` liegt in der Vergangenheit."

    iso_str = target_date.isoformat()
    cfg["pause_until"] = iso_str
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    days_diff = (target_date - ref_today).days
    return (
        True,
        f"⏸️ **Flug-Schnäppchen-Radar pausiert bis einschließlich {iso_str}** ({days_diff} Tag(e)). "
        f"Bis dahin werden keine Suchläufe oder Benachrichtigungen ausgeführt.",
    )


def add_exclusion(
    target: str,
    blacklist_path: Path = DEFAULT_BLACKLIST_PATH,
) -> Tuple[bool, str]:
    """
    Fügt einen Ort zur Blacklist hinzu.
    Unterstützt:
      - 3-Buchstaben IATA-Code: `TIA`, `STN`
      - Explizites Präfix: `city:Tirana`, `country:Albanien`, `airport:TIA`
      - Städtename im Klartext: `Tirana`
    """
    raw = (target or "").strip()
    if not raw:
        return False, "Kein Ziel zum Ausschließen angegeben."

    bl = load_blacklist(blacklist_path)
    airports: List[str] = bl.setdefault("excluded_airports", [])
    cities: List[str] = bl.setdefault("excluded_cities", [])
    countries: List[str] = bl.setdefault("excluded_countries", [])

    lower = raw.lower()
    if lower.startswith("country:") or lower.startswith("land:"):
        country_val = raw.split(":", 1)[1].strip()
        if country_val and country_val not in countries:
            countries.append(country_val)
            save_blacklist(bl, blacklist_path)
            return True, f"Land **{country_val}** wurde dauerhaft auf die Blacklist gesetzt."
        return False, f"Land **{country_val}** war bereits auf der Blacklist."

    if lower.startswith("city:") or lower.startswith("stadt:"):
        city_val = raw.split(":", 1)[1].strip()
        if city_val and city_val not in cities:
            cities.append(city_val)
            save_blacklist(bl, blacklist_path)
            return True, f"Stadt **{city_val}** wurde dauerhaft auf die Blacklist gesetzt."
        return False, f"Stadt **{city_val}** war bereits auf der Blacklist."

    if lower.startswith("airport:"):
        raw = raw.split(":", 1)[1].strip()

    # Prüfe, ob es ein 3-Buchstaben-IATA-Code ist
    if re.fullmatch(r"[A-Za-z]{3}", raw):
        code = raw.upper()
        city_name, _ = resolve_city_and_country(code)
        if code not in airports:
            airports.append(code)
            save_blacklist(bl, blacklist_path)
            return True, f"Flughafen **{code}** ({city_name}) wurde dauerhaft auf die Blacklist gesetzt."
        return False, f"Flughafen **{code}** ({city_name}) stand bereits auf der Blacklist."

    # Andernfalls als Stadtname behandeln
    if raw not in cities:
        cities.append(raw)
        save_blacklist(bl, blacklist_path)
        return True, f"Ort **{raw}** wurde dauerhaft auf die Blacklist gesetzt."
    return False, f"Ort **{raw}** stand bereits auf der Blacklist."


def remove_exclusion(
    target: str,
    blacklist_path: Path = DEFAULT_BLACKLIST_PATH,
) -> Tuple[bool, str]:
    """Entfernt einen Flughafen, eine Stadt oder ein Land wieder von der Blacklist."""
    raw = (target or "").strip()
    if not raw:
        return False, "Kein Ziel zum Entfernen von der Blacklist angegeben."

    bl = load_blacklist(blacklist_path)
    airports: List[str] = bl.setdefault("excluded_airports", [])
    cities: List[str] = bl.setdefault("excluded_cities", [])
    countries: List[str] = bl.setdefault("excluded_countries", [])

    cleaned = re.sub(r"^(?:country|land|city|stadt|airport)\s*:\s*", "", raw, flags=re.IGNORECASE).strip()
    removed_any = False

    # Aus Flughäfen entfernen (Case-Insensitive)
    matching_airports = [a for a in airports if a.upper() == cleaned.upper()]
    for a in matching_airports:
        airports.remove(a)
        removed_any = True

    # Aus Städten entfernen (Case-Insensitive)
    matching_cities = [c for c in cities if c.lower() == cleaned.lower()]
    for c in matching_cities:
        cities.remove(c)
        removed_any = True

    # Aus Ländern entfernen (Case-Insensitive)
    matching_countries = [co for co in countries if co.lower() == cleaned.lower()]
    for co in matching_countries:
        countries.remove(co)
        removed_any = True

    if removed_any:
        save_blacklist(bl, blacklist_path)
        return True, f"**{cleaned}** wurde wieder von der Blacklist entfernt."
    return False, f"**{cleaned}** wurde nicht auf der Blacklist gefunden."


def add_deal_exclusion(
    signature: str,
    exclusions_path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
) -> Tuple[bool, str]:
    deal_signature = (signature or "").strip()
    if not DEAL_SIGNATURE_PATTERN.fullmatch(deal_signature):
        return False, "Ungültige Deal-ID. Erwartet wird `AAA-BBB:YYYY-MM-DD:YYYY-MM-DD`."

    exclusions = load_deal_exclusions(exclusions_path)
    if deal_signature in exclusions:
        return False, f"Deal **{deal_signature}** war bereits ausgeschlossen."

    exclusions.add(deal_signature)
    save_deal_exclusions(exclusions, exclusions_path)
    return True, f"Nur der Deal **{deal_signature}** wurde dauerhaft ausgeschlossen."


def remove_deal_exclusion(
    signature: str,
    exclusions_path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
) -> Tuple[bool, str]:
    deal_signature = (signature or "").strip()
    exclusions = load_deal_exclusions(exclusions_path)
    if deal_signature not in exclusions:
        return False, f"Deal **{deal_signature}** war nicht in den Deal-Ausschlüssen enthalten."

    exclusions.remove(deal_signature)
    save_deal_exclusions(exclusions, exclusions_path)
    return True, f"Deal-Ausschluss **{deal_signature}** wurde wieder aufgehoben."


def add_or_update_wishlist(
    code: str,
    max_price_eur: float,
    name: Optional[str] = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Tuple[bool, str]:
    """Fügt ein Wunschziel in `config/search_config.yaml` hinzu oder aktualisiert dessen Maximalpreis."""
    iata = code.upper().strip()
    if not re.fullmatch(r"[A-Z]{3}", iata):
        return False, f"Ungültiger IATA-Code: `{code}` (erwartet: 3 Buchstaben wie `LIS` oder `PMI`)."

    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    wishlist: List[dict] = cfg.setdefault("wishlist_destinations", [])
    city_name, country_name = resolve_city_and_country(iata, fallback_city=name or "")

    for item in wishlist:
        if (item.get("code") or "").upper() == iata:
            item["max_price_eur"] = float(max_price_eur)
            if name:
                item["name"] = name
            with config_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
            return True, f"Wunschziel **{item.get('name', iata)} ({iata})** aktualisiert auf max. **{max_price_eur:.0f} €**."

    wishlist.append(
        {
            "code": iata,
            "name": name or city_name,
            "country": country_name,
            "max_price_eur": float(max_price_eur),
        }
    )
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    return True, f"Neues Wunschziel **{name or city_name} ({iata})** mit Limit **{max_price_eur:.0f} €** hinzugefügt."


def remove_wishlist(
    code: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Tuple[bool, str]:
    """Entfernt ein Wunschziel anhand des IATA-Codes oder Namens aus `config/search_config.yaml`."""
    cleaned = code.strip()
    if not cleaned:
        return False, "Kein Wunschziel angegeben."

    with config_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    wishlist: List[dict] = cfg.get("wishlist_destinations") or []
    kept: List[dict] = []
    removed_labels: List[str] = []

    for item in wishlist:
        item_code = str(item.get("code", "")).strip()
        item_name = str(item.get("name", item_code)).strip()
        if item_code.upper() == cleaned.upper() or item_name.lower() == cleaned.lower():
            removed_labels.append(f"{item_name} ({item_code.upper()})")
        else:
            kept.append(item)

    if not removed_labels:
        return False, f"Wunschziel **{cleaned}** war nicht in der Wunschliste enthalten."

    cfg["wishlist_destinations"] = kept
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    return True, f"Wunschziel **{', '.join(removed_labels)}** aus der Wunschliste entfernt."


def trigger_test_discord(
    config_path: Path = DEFAULT_CONFIG_PATH,
    blacklist_path: Path = DEFAULT_BLACKLIST_PATH,
    deal_exclusions_path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
) -> Tuple[bool, str]:
    """
    Merkt den nächsten Suchlauf garantiert für eine Discord-Testnachricht vor (`force_next_discord: true`)
    und sendet – falls `DISCORD_WEBHOOK_URL` gesetzt ist – sofort eine Discord-Zusammenfassung der aktuellen Top-Deals.
    """
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    cfg["force_next_discord"] = True
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if webhook:
        try:
            from src.active_deals import DEFAULT_ACTIVE_DEALS_PATH, load_active_deals
            from src.deal_page import get_deals_page_url
            from src.notifiers.discord import DiscordNotifier

            bl = load_blacklist(blacklist_path)
            ex_airports = {a.upper().strip() for a in bl.get("excluded_airports", [])}
            ex_cities = {c.lower().strip() for c in bl.get("excluded_cities", [])}
            ex_countries = {co.lower().strip() for co in bl.get("excluded_countries", [])}
            ex_sigs = load_deal_exclusions(deal_exclusions_path)

            active = [
                d
                for d in load_active_deals(DEFAULT_ACTIVE_DEALS_PATH)
                if d.offer.deal_signature not in ex_sigs
                and d.offer.destination.upper() not in ex_airports
                and d.offer.destination_name.lower().strip() not in ex_cities
                and d.offer.destination_country.lower().strip() not in ex_countries
            ]
            active.sort(key=lambda d: (-d.deal_score, d.offer.price_eur))
            top_deals = active[:10]

            page_url = (
                get_deals_page_url(configured_url=os.getenv("FLIGHT_DEALS_PAGE_URL", ""))
                or get_deals_page_url(repository="KayToTheRopf/FlightScannerMK")
            )
            if top_deals and DiscordNotifier(webhook_url=webhook).send_deal_summary(top_deals, page_url):
                return (
                    True,
                    f"🔔 **Test-Discord mit {len(top_deals)} Top-Schnäppchen wurde sofort gesendet!** "
                    f"(Zusätzlich ist `force_next_discord: true` für den nächsten Suchlauf aktiv.)",
                )
        except Exception as exc:
            logger.debug("Sofortiger Discord-Testversand fehlgeschlagen: %s", exc)

    return (
        True,
        "🔔 **Nächster Discord-Versand zum Testen aktiviert (`force_next_discord: true`)!** "
        "Beim nächsten Suchlauf wird garantiert eine Discord-Benachrichtigung gesendet.",
    )


def parse_and_execute_feedback(
    text: str,
    blacklist_path: Path = DEFAULT_BLACKLIST_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    deal_exclusions_path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
    today: Optional[date] = None,
) -> List[str]:
    """
    Parst Issue-Titel oder Issue-Kommentare nach Feedback-Befehlen:
      - `ignore-deal:<SIGNATUR>` (aus 1-Klick-Link im Deal)
      - `unexclude-deal:<SIGNATUR>` oder `/unexclude-deal <SIGNATUR>`
      - `exclude:TIA` (aus einem 1-Klick-Link)
      - `unexclude:TIA` oder `/unexclude TIA` (Ort wieder von Blacklist entfernen)
      - `/exclude TIA` oder `!exclude city:Tirana` oder `/ignore STN`
      - `watch:LIS:110` oder `watch:PMI:65:Palma de Mallorca` oder `/watch LIS 110 [Name=...]`
      - `unwatch:LIS` oder `/unwatch LIS`
      - `pause:7d`, `/pause 14d`, `/pause 2026-12-01`, `/resume`, `resume:now`
      - `test-discord`, `discord:test`, `/test-discord`, `/discord`
    """
    messages: List[str] = []
    if not text:
        return messages

    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        # 0) Test-Discord anfordern per Issue-Titel ("test-discord", "discord:test") oder Kommentar ("/test-discord", "/discord")
        m_discord_title = re.match(
            r"^(?:test-discord|discord-test|send-discord|discord\s*:\s*test)$",
            line_clean,
            flags=re.IGNORECASE,
        )
        if m_discord_title:
            _, msg = trigger_test_discord(
                config_path=config_path,
                blacklist_path=blacklist_path,
                deal_exclusions_path=deal_exclusions_path,
            )
            messages.append(msg)
            continue

        m_discord_cmd = re.match(
            r"^[/!](?:test-discord|discord-test|send-discord|discord)(?:\s+.*)?$",
            line_clean,
            flags=re.IGNORECASE,
        )
        if m_discord_cmd:
            _, msg = trigger_test_discord(
                config_path=config_path,
                blacklist_path=blacklist_path,
                deal_exclusions_path=deal_exclusions_path,
            )
            messages.append(msg)
            continue

        # 0a) Radar pausieren / fortsetzen per Issue-Titel: "pause: 7d", "pause: 2026-12-01", "resume: now"
        m_pause_title = re.match(r"^(?:pause|pausieren)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_pause_title:
            _, msg = set_radar_pause(m_pause_title.group(1).strip(), config_path=config_path, today=today)
            messages.append(msg)
            continue

        m_resume_title = re.match(r"^(?:resume|unpause|weiter)(?:\s*:\s*(.*))?$", line_clean, flags=re.IGNORECASE)
        if m_resume_title:
            _, msg = set_radar_pause("off", config_path=config_path, today=today)
            messages.append(msg)
            continue

        # 0b) Radar pausieren / fortsetzen per Kommentar: "/pause 7d", "/pause 2026-12-01", "/resume", "/weiter"
        m_pause_cmd = re.match(r"^[/!](?:pause|pausieren)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_pause_cmd:
            _, msg = set_radar_pause(m_pause_cmd.group(1).strip(), config_path=config_path, today=today)
            messages.append(msg)
            continue

        m_resume_cmd = re.match(r"^[/!](?:resume|unpause|weiter)(?:\s+.*)?$", line_clean, flags=re.IGNORECASE)
        if m_resume_cmd:
            _, msg = set_radar_pause("off", config_path=config_path, today=today)
            messages.append(msg)
            continue

        # 1a) Deal-Ausschluss wieder aufheben: "unexclude-deal:FMM-PMI:2026-06-10:2026-06-17" oder "/unexclude-deal ..."
        m_undeal_title = re.match(r"^(?:unexclude-deal|unignore-deal)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_undeal_title:
            _, msg = remove_deal_exclusion(m_undeal_title.group(1).strip(), exclusions_path=deal_exclusions_path)
            messages.append(msg)
            continue

        m_undeal_cmd = re.match(r"^[/!](?:unexclude-deal|unignore-deal)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_undeal_cmd:
            _, msg = remove_deal_exclusion(m_undeal_cmd.group(1).strip(), exclusions_path=deal_exclusions_path)
            messages.append(msg)
            continue

        # 1b) 1-Klick-Issue-Titel: "ignore-deal:FMM-PMI:2026-06-10:2026-06-17"
        m_deal_title = re.match(r"^(?:ignore-deal|exclude-deal)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_deal_title:
            _, msg = add_deal_exclusion(m_deal_title.group(1).strip(), exclusions_path=deal_exclusions_path)
            messages.append(msg)
            continue

        # 2) Deal per Kommentar ausschließen
        m_deal_cmd = re.match(r"^[/!](?:ignore-deal|exclude-deal)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_deal_cmd:
            _, msg = add_deal_exclusion(m_deal_cmd.group(1).strip(), exclusions_path=deal_exclusions_path)
            messages.append(msg)
            continue

        # 2b) Ort wieder von Blacklist entfernen: "unexclude:TIA" oder "/unexclude TIA"
        m_un_title = re.match(r"^(?:unexclude|unignore|unblacklist)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_un_title:
            _, msg = remove_exclusion(m_un_title.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        m_un_cmd = re.match(r"^[/!](?:unexclude|unignore|unblacklist)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_un_cmd:
            _, msg = remove_exclusion(m_un_cmd.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        # 3) 1-Klick- oder manuelle Issue-Titel: "exclude:TIA", "ignore: Banja luka", "blacklist: BNX"
        m_title = re.match(r"^(?:exclude|ignore|blacklist\w*)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_title:
            _, msg = add_exclusion(m_title.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        # 4) Kommentar-Befehl: "/exclude <ziel>" oder "!exclude <ziel>" oder "/ignore <ziel>"
        m_cmd = re.match(r"^[/!](?:exclude|ignore|blacklist\w*)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_cmd:
            _, msg = add_exclusion(m_cmd.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        # 5a) Wunschziel entfernen per Issue-Titel ("unwatch:LIS") oder Kommentar ("/unwatch LIS")
        m_unwatch_title = re.match(r"^(?:unwatch|remove-watch)\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_unwatch_title:
            _, msg = remove_wishlist(m_unwatch_title.group(1).strip(), config_path=config_path)
            messages.append(msg)
            continue

        m_unwatch_cmd = re.match(r"^[/!](?:unwatch|remove-watch)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_unwatch_cmd:
            _, msg = remove_wishlist(m_unwatch_cmd.group(1).strip(), config_path=config_path)
            messages.append(msg)
            continue

        # 5b) Wunschziel hinzufügen/aktualisieren per Issue-Titel ("watch:LIS:110" oder "watch:PMI:65:Mallorca")
        m_watch_title = re.match(
            r"^(?:watch|wishlist)\s*:\s*([A-Za-z]{3})\s*:\s*(\d+(?:[.,]\d+)?)(?:\s*:\s*(.+))?$",
            line_clean,
            flags=re.IGNORECASE,
        )
        if m_watch_title:
            code = m_watch_title.group(1)
            price = float(m_watch_title.group(2).replace(",", "."))
            custom_name = m_watch_title.group(3).strip() if m_watch_title.group(3) else None
            _, msg = add_or_update_wishlist(code, price, name=custom_name, config_path=config_path)
            messages.append(msg)
            continue

        # 5c) Kommentar-Befehl: "/watch <IATA> <PREIS> [Name=...]"
        m_watch = re.match(
            r"^[/!](?:watch|add|maxprice)\s+([A-Za-z]{3})\s+(\d+(?:[.,]\d+)?)(?:\s+Name=(.+))?$",
            line_clean,
            flags=re.IGNORECASE,
        )
        if m_watch:
            code = m_watch.group(1)
            price = float(m_watch.group(2).replace(",", "."))
            custom_name = m_watch.group(3).strip() if m_watch.group(3) else None
            _, msg = add_or_update_wishlist(code, price, name=custom_name, config_path=config_path)
            messages.append(msg)

    return messages


def notify_feedback_result(messages: List[str], issue_number: Optional[int] = None) -> None:
    if not messages:
        return
    summary = "✅ **Feedback verarbeitet:**\n" + "\n".join(f"- {m}" for m in messages)
    print(summary)

    # Optional an Discord melden
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if webhook:
        try:
            requests.post(webhook, json={"content": summary}, timeout=10)
        except Exception as exc:
            logger.debug("Discord Feedback-Bestätigung fehlgeschlagen: %s", exc)

    # Optional auf GitHub Issue antworten & bei 1-Klick-Exclude-Issue automatisch schließen
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if token and repo and issue_number:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        base_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        try:
            requests.post(f"{base_url}/comments", headers=headers, json={"body": summary}, timeout=10)
            if os.getenv("CLOSE_ISSUE_AFTER_FEEDBACK", "false").lower() == "true":
                requests.patch(base_url, headers=headers, json={"state": "closed"}, timeout=10)
        except Exception as exc:
            logger.debug("GitHub Issue-Kommentar fehlgeschlagen: %s", exc)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verarbeitet Rückmeldungen (Blacklist, Deal-Ausschlüsse & Wunschliste)")
    parser.add_argument("--input", type=str, default="", help="Befehlstext oder Issue-Titel (z.B. 'ignore-deal:...' oder '/exclude TIA')")
    parser.add_argument("--issue-number", type=int, default=None, help="Optionale GitHub Issue-Nummer für Antwort/Schließen")
    parser.add_argument("--blacklist", type=Path, default=DEFAULT_BLACKLIST_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--deal-exclusions", type=Path, default=DEFAULT_DEAL_EXCLUSIONS_PATH)
    args = parser.parse_args(argv)

    input_text = args.input or os.getenv("FEEDBACK_TEXT", "")
    issue_num = args.issue_number or (int(os.getenv("ISSUE_NUMBER")) if os.getenv("ISSUE_NUMBER", "").isdigit() else None)

    messages = parse_and_execute_feedback(
        text=input_text,
        blacklist_path=args.blacklist,
        config_path=args.config,
        deal_exclusions_path=args.deal_exclusions,
    )
    if not messages:
        print("Keine passenden Feedback-Befehle im Text gefunden.")
        return 0

    notify_feedback_result(messages, issue_number=issue_num)
    return 0


if __name__ == "__main__":
    sys.exit(main())
