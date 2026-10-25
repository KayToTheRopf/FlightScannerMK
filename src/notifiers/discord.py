from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

import requests

from src.models import EvaluatedDeal

logger = logging.getLogger(__name__)

MAX_EMBEDS_PER_MESSAGE = 10
MAX_EMBED_TEXT_PER_MESSAGE = 6000
MAX_EMBED_DESCRIPTION_LENGTH = 4096
MAX_EMBED_TITLE_LENGTH = 256


class DiscordNotifier:
    """
    Sendet gefundene Flugschnäppchen als übersichtliche Discord Rich-Embeds.
    Jedes Schnäppchen enthält:
      - Direktlink zur Buchung / Google Flights
      - 1-Klick-Link '[🚫 Ort ausschließen]', der ein vorausgefülltes GitHub Issue öffnet
    """

    def __init__(self, webhook_url: Optional[str] = None, timeout: int = 15) -> None:
        self.webhook_url = (webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")).strip()
        self.timeout = timeout

    def send_deals(self, deals: List[EvaluatedDeal]) -> bool:
        if not deals:
            return False
        if not self.webhook_url:
            logger.info("DiscordNotifier: Kein DISCORD_WEBHOOK_URL konfiguriert – überspringe Discord-Versand.")
            return False

        embeds = []
        for deal in deals:
            o = deal.offer
            badge = "⭐ WUNSCHZIEL" if o.is_wishlist else "🌍 EXPLORE-DEAL"
            stops_text = "Direktflug" if o.stops == 0 else f"{o.stops} Stopp(s)"
            avg_text = f"{deal.historical_avg_eur:.0f} €" if deal.historical_avg_eur else "n/a"

            description = (
                f"**{o.origin_name} ({o.origin}) ➔ {o.destination_name} ({o.destination}), {o.destination_country}**\n"
                f"📅 **Reisezeitraum:** `{o.outbound_date}` bis `{o.inbound_date}` ({o.stay_days} Tage)\n"
                f"💶 **Preis (Hin & Zurück):** **{o.price_eur:.2f} €** *(Limit: {deal.threshold_eur:.0f} € | Ø: {avg_text})*\n"
                f"🔥 **Ersparnis:** {deal.reason}\n"
                f"✈️ **Airline:** {o.airline} ({stops_text}) via `{o.provider}`\n\n"
                f"👉 **[✈️ Flug ansehen & buchen]({o.booking_url})**  |  "
                f"**[🚫 {o.destination_name} künftig ausschließen]({deal.exclude_url})**"
            )

            title = f"{badge}: {o.destination_name} für {o.price_eur:.0f} € (ab {o.origin})"
            if len(title) > MAX_EMBED_TITLE_LENGTH or len(description) > MAX_EMBED_DESCRIPTION_LENGTH:
                logger.warning(
                    "DiscordNotifier: Deal %s-%s überschreitet das Zeichenlimit eines Embeds.",
                    o.origin,
                    o.destination,
                )
                return False

            color = 0x2ECC71 if o.is_wishlist else 0x3498DB
            embeds.append(
                {
                    "title": title,
                    "description": description,
                    "color": color,
                }
            )

        batches: List[List[dict]] = []
        current_batch: List[dict] = []
        current_size = 0
        for embed in embeds:
            embed_size = len(embed["title"]) + len(embed["description"])
            if current_batch and (
                len(current_batch) >= MAX_EMBEDS_PER_MESSAGE
                or current_size + embed_size > MAX_EMBED_TEXT_PER_MESSAGE
            ):
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(embed)
            current_size += embed_size
        if current_batch:
            batches.append(current_batch)

        try:
            for batch_number, batch in enumerate(batches, start=1):
                payload = {
                    "username": "✈️ Schnäppchen-Radar (MUC & FMM)",
                    "content": (
                        f"🎯 **{len(deals)} echte Flugschnäppchen gefunden!** "
                        f"*(Stand: {datetime.now().strftime('%d.%m.%Y %H:%M')})*\n"
                        "💡 *Tipp: Klicke bei einem Deal auf `🚫 künftig ausschließen`, "
                        "um den Ort auf die Blacklist zu setzen.*"
                    ),
                    "embeds": batch,
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
                if resp.status_code not in (200, 204):
                    logger.warning(
                        "DiscordNotifier: Nachricht %d/%d fehlgeschlagen (HTTP %s) – %s",
                        batch_number,
                        len(batches),
                        resp.status_code,
                        resp.text[:200],
                    )
                    return False

            logger.info(
                "DiscordNotifier: %d Deals in %d Nachricht(en) erfolgreich gesendet.",
                len(deals),
                len(batches),
            )
            return True
        except Exception as exc:
            logger.error("DiscordNotifier Fehler: %s", exc)
            return False
