from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from src.models import EvaluatedDeal

logger = logging.getLogger(__name__)


class EmailSmtpNotifier:
    """
    Sendet eine formatierte HTML-E-Mail mit allen Schnäppchen und 1-Klick-Buttons
    zum Buchen sowie zum Ausschließen einzelner Deals (`[🚫 Diesen Deal ausschließen]`).
    """

    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "").strip()
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "").strip()
        self.password = os.getenv("SMTP_PASSWORD", "").strip()
        self.recipient = os.getenv("EMAIL_TO", self.user).strip()

    def send_deals(self, deals: List[EvaluatedDeal]) -> bool:
        if not deals:
            return False
        if not (self.host and self.user and self.password and self.recipient):
            logger.info("EmailSmtpNotifier: SMTP-Zugangsdaten nicht vollständig gesetzt – überspringe E-Mail.")
            return False

        best = deals[0].offer
        subject = f"✈️ {len(deals)} Flugschnäppchen ab MUC/FMM: z.B. {best.destination_name} für {best.price_eur:.0f} €"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = self.recipient

        html_body = self._build_html(deals)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, [self.recipient], msg.as_string())
            logger.info("EmailSmtpNotifier: HTML-Mail erfolgreich an %s gesendet.", self.recipient)
            return True
        except Exception as exc:
            logger.error("EmailSmtpNotifier Fehler: %s", exc)
            return False

    @staticmethod
    def _build_html(deals: List[EvaluatedDeal]) -> str:
        rows = []
        for d in deals:
            o = d.offer
            badge = "⭐ Wunschziel" if o.is_wishlist else "🌍 Explore"
            rows.append(
                f"<tr>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;'>{badge}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;'><b>{o.origin} ➔ {o.destination_name}</b> ({o.destination}, {o.destination_country})</td>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;'>{o.outbound_date} bis {o.inbound_date} ({o.stay_days} Tage)</td>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;color:#1b8a3d;font-weight:bold;'>{o.price_eur:.2f} €</td>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;'>{d.reason}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #ddd;'>"
                f"<a href='{o.booking_url}' style='background:#0066cc;color:#fff;padding:5px 10px;text-decoration:none;border-radius:4px;'>✈️ Zum Flug</a> "
                f"<a href='{d.exclude_url}' style='background:#cc3300;color:#fff;padding:5px 10px;text-decoration:none;border-radius:4px;'>🚫 Deal ausschließen</a>"
                f"</td>"
                f"</tr>"
            )
        rows_html = "\n".join(rows)
        return (
            "<html><body style='font-family:Arial,sans-serif;'>"
            "<h2>🎯 Neue echte Flugschnäppchen (München & Memmingen)</h2>"
            "<table style='border-collapse:collapse;width:100%;'>"
            "<thead><tr style='background:#f4f4f4;text-align:left;'>"
            "<th style='padding:8px;'>Typ</th><th style='padding:8px;'>Route</th>"
            "<th style='padding:8px;'>Zeitraum</th><th style='padding:8px;'>Preis</th>"
            "<th style='padding:8px;'>Bewertung</th><th style='padding:8px;'>Aktion</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody></table>"
            "<p style='color:#666;font-size:12px;margin-top:16px;'>"
            "Tipp: Ein Klick auf '🚫 Deal ausschließen' öffnet ein vorausgefülltes GitHub-Issue, "
            "das nur diese Route mit diesem Reisezeitraum ausblendet."
            "</p></body></html>"
        )
