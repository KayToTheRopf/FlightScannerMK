from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

import requests

from src.models import EvaluatedDeal

logger = logging.getLogger(__name__)


class GitHubIssueNotifier:
    """
    Erstellt bei gefundenen Schnäppchen ein übersichtliches GitHub Issue im Repository.
    Vorteil:
      1. GitHub schickt automatisch eine Push-/E-Mail-Benachrichtigung.
      2. Du kannst direkt unter dem Issue kommentieren (oder auf die GitHub-Mail antworten!):
         - `/exclude TIA` oder `/exclude Tirana` -> schließt den Ort dauerhaft aus
         - `/watch LIS 110` -> fügt Lissabon mit 110 € Limit zur Wunschliste hinzu
      3. Alternativ funktioniert auch der 1-Klick-Link `[🚫 Ausschließen]` in der Tabelle.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        label: str = "flight-deal",
        timeout: int = 15,
    ) -> None:
        self.token = (token or os.getenv("GITHUB_TOKEN", "")).strip()
        self.repo = (repo or os.getenv("GITHUB_REPOSITORY", "")).strip()
        self.label = label
        self.timeout = timeout

    def send_deals(self, deals: List[EvaluatedDeal]) -> bool:
        if not deals:
            return False
        if not self.token or not self.repo:
            logger.info(
                "GitHubIssueNotifier: GITHUB_TOKEN oder GITHUB_REPOSITORY fehlt – überspringe Issue-Erstellung."
            )
            return False

        today_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        best = deals[0].offer
        title = (
            f"✈️ {len(deals)} Flugschnäppchen ({today_str}): "
            f"z.B. {best.origin} ➔ {best.destination_name} ab {best.price_eur:.0f} €"
        )
        body = self.format_markdown_report(deals)

        url = f"https://api.github.com/repos/{self.repo}/issues"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {
            "title": title,
            "body": body,
            "labels": [self.label],
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code in (200, 201):
                issue_url = resp.json().get("html_url", "")
                logger.info("GitHubIssueNotifier: Issue erstellt (%s)", issue_url)
                return True
            logger.warning("GitHubIssueNotifier: HTTP %s – %s", resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.error("GitHubIssueNotifier Fehler: %s", exc)
            return False

    @staticmethod
    def format_markdown_report(deals: List[EvaluatedDeal]) -> str:
        lines = [
            "## 🎯 Gefundene Flugschnäppchen (Hin- & Rückflug)",
            "",
            "| Typ | Route | Reisezeitraum | Dauer | Preis | Ersparnis | Airline | Aktionen |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for d in deals:
            o = d.offer
            badge = "⭐ Wunschziel" if o.is_wishlist else "🌍 Explore"
            stops = "Direkt" if o.stops == 0 else f"{o.stops} Stopp"
            route_str = f"**{o.origin}** ➔ **{o.destination_name}** (`{o.destination}`, {o.destination_country})"
            dates_str = f"`{o.outbound_date}` – `{o.inbound_date}`"
            price_str = f"**{o.price_eur:.2f} €**"
            actions = f"[✈️ Buchen]({o.booking_url}) · [🚫 Ort ausschließen]({d.exclude_url})"
            lines.append(
                f"| {badge} | {route_str} | {dates_str} | {o.stay_days} Tage | {price_str} | {d.reason} | {o.airline} ({stops}) | {actions} |"
            )

        lines.extend(
            [
                "",
                "---",
                "### 💬 Interaktive Steuerung (Rückmeldung geben)",
                "Du kannst Orte ganz einfach ausschließen oder deine Wunschliste anpassen:",
                "1. **Per 1-Klick:** Klicke in der Tabelle oben bei einem Ziel auf **`[🚫 Ort ausschließen]`** und bestätige das Ticket.",
                "2. **Per Kommentar unter diesem Issue (oder per E-Mail-Antwort):**",
                "   - `/exclude TIA` *(schließt den Flughafen-Code TIA dauerhaft aus)*",
                "   - `/exclude city:Tirana` *(schließt die Stadt Tirana aus)*",
                "   - `/exclude country:Albanien` *(schließt ein ganzes Land aus)*",
                "   - `/watch LIS 110 Name=Lissabon` *(fügt ein neues Wunschziel mit Maximalpreis hinzu)*",
            ]
        )
        return "\n".join(lines)
