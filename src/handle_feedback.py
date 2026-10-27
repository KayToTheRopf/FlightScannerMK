from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import yaml

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


def parse_and_execute_feedback(
    text: str,
    blacklist_path: Path = DEFAULT_BLACKLIST_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    deal_exclusions_path: Path = DEFAULT_DEAL_EXCLUSIONS_PATH,
) -> List[str]:
    """
    Parst Issue-Titel oder Issue-Kommentare nach Feedback-Befehlen:
      - `ignore-deal:<SIGNATUR>` (aus 1-Klick-Link im Deal)
      - `exclude:TIA` (aus einem älteren 1-Klick-Link)
      - `/exclude TIA` oder `!exclude city:Tirana` oder `/ignore STN`
      - `/watch LIS 110` oder `/watch PMI 65 Name=Mallorca`
    """
    messages: List[str] = []
    if not text:
        return messages

    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        # 1) 1-Klick-Issue-Titel: "ignore-deal:FMM-PMI:2026-06-10:2026-06-17"
        m_deal_title = re.match(r"^ignore-deal\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
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

        # 3) Älterer 1-Klick-Issue-Titel: "exclude:TIA"
        m_title = re.match(r"^exclude\s*:\s*(.+)$", line_clean, flags=re.IGNORECASE)
        if m_title:
            _, msg = add_exclusion(m_title.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        # 4) Kommentar-Befehl: "/exclude <ziel>" oder "!exclude <ziel>" oder "/ignore <ziel>"
        m_cmd = re.match(r"^[/!](?:exclude|ignore|blacklist)\s+(.+)$", line_clean, flags=re.IGNORECASE)
        if m_cmd:
            _, msg = add_exclusion(m_cmd.group(1).strip(), blacklist_path=blacklist_path)
            messages.append(msg)
            continue

        # 5) Kommentar-Befehl: "/watch <IATA> <PREIS> [Name=...]"
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
