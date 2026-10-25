# ✈️ Automatisches Flug-Schnäppchen-Radar (München `MUC` & Memmingen `FMM`)

Vollautomatische, **100 % kostenlose** Flugpreis-Suche für Hin- und Rückflüge (3–14 Tage Aufenthalt in den nächsten 6 Monaten) ab **München (`MUC`)** und **Memmingen (`FMM`)**.

Läuft **2x täglich in der Cloud über GitHub Actions** (dein PC muss nicht eingeschaltet sein) und benachrichtigt dich nur bei **echten Schnäppchen** über **Discord**, **GitHub Issues** oder **E-Mail** – inklusive **1-Klick-Rückmeldung**, um uninteressante Orte dauerhaft auszuschließen (`Blacklist`).

---

## 🏗️ Architektur-Überblick

1. **Warum Python-Module statt einzelner MCPs für den Hintergrundjob?**
   - Für den automatischen Lauf 2x am Tag startet GitHub Actions direkt das Python-Skript `src/run_search.py`.
   - Dieses ruft die drei API-Module (`src/providers/ryanair.py`, `src/providers/travelpayouts.py`, `src/providers/google_flights.py`) direkt in Python auf – schnell, kostenlos und ohne LLM-/Token-Kosten.
   - **Optional für VS Code:** Falls du *zusätzlich* hier im VS-Code-Chat interaktiv nach Flügen fragen oder deine Blacklist per Chat verwalten möchtest, bündelt **ein einziger** MCP-Server (`src/mcp_server.py`) alle 3 APIs und deine Konfigurationsdateien.

2. **Dreifach-API-Strategie (kostenlos):**
   - **Ryanair FareFinder API (`ryanair.py`):** Kein API-Key nötig! Durchsucht ab `FMM` (und `MUC`-Umland) live alle „Überallhin“-Ziele für 3–14 Tage Aufenthalt.
   - **Travelpayouts / Aviasales Data API (`travelpayouts.py`):** Kostenloser API-Token. Ideal für die „Überallhin“-Suche und Monats-Matrizen ab München (`MUC`) und Memmingen (`FMM`).
   - **Google Flights Engine (`google_flights.py` via `fast-flights`):** Kein API-Key nötig! Prüft gezielt deine festen **Wunschziele** ab `MUC` & `FMM` und verifiziert gecachte Travelpayouts-Treffer live.

3. **Echte Schnäppchen-Erkennung (`src/analyzer.py`):**
   - Vergleicht jeden Flug mit deiner Preisgrenze (`config/search_config.yaml`) **und** dem gleitenden historischen Durchschnittspreis der Route (`data/price_history.json`).
   - Verhindert doppelte Meldungen durch einen 7-Tage-Cooldown (es sei denn, der Preis fällt nochmals um mindestens 15 %).

4. **Interaktive Rückmeldung – Orte mit 1 Klick ausschließen (`src/handle_feedback.py`):**
   - Jede Benachrichtigung (egal ob in Discord, GitHub oder per E-Mail) enthält neben dem `[✈️ Flug ansehen & buchen]`-Link einen **`[🚫 Ort künftig ausschließen]`**-Link.
   - Klickst du darauf, öffnet sich ein vorausgefülltes GitHub-Issue (`exclude:TIA`). Nach einem Tipp auf *„Submit new issue“* trägt die GitHub Action (`feedback_handler.yml`) den Ort automatisch in `config/blacklist.json` ein, bestätigt es auf Discord/GitHub und schließt das Issue wieder.
   - **Alternativ per Kommentar (oder E-Mail-Antwort auf ein GitHub-Issue):**
     - `/exclude TIA` (schließt Flughafen TIA aus)
     - `/exclude city:Tirana` (schließt Stadt Tirana aus)
     - `/exclude country:Albanien` (schließt ganzes Land aus)
     - `/watch LIS 110 Name=Lissabon` (fügt Wunschziel mit Maximalpreis hinzu)

---

## 🚀 Schnellstart & Einrichtung (in 5 Minuten)

### 1. Repository auf GitHub pushen
Lege ein neues (privates oder öffentliches) GitHub-Repository an und pushe diese Dateien dorthin.

### 2. Kostenlose Secrets in GitHub hinterlegen (Optional, je nach Wunsch-Kanal)
Gehe in deinem GitHub-Repository auf **Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**:

| Secret-Name | Pflicht? | Beschreibung |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | Automatisch da | Wird von GitHub Actions automatisch bereitgestellt (erstellt GitHub Issues bei Schnäppchen). |
| `DISCORD_WEBHOOK_URL` | Empfohlen | In Discord: *Kanal bearbeiten ➔ Integrationen ➔ Webhooks ➔ Neuer Webhook ➔ Webhook-URL kopieren*. |
| `TRAVELPAYOUTS_TOKEN` | Empfohlen für MUC | Kostenlos registrieren auf [travelpayouts.com](https://www.travelpayouts.com/), unter *Profile ➔ API Token* kopieren. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` | Optional | Nur falls du zusätzlich klassische HTML-E-Mails (und `notifications.email.enabled: true` in `search_config.yaml`) nutzen möchtest. |

### 3. Wunschziele & Preisgrenzen anpassen
In [`config/search_config.yaml`](./config/search_config.yaml) kannst du jederzeit:
- die globalen „Überallhin“-Preisgrenzen für Memmingen (`max_explore_price_eur: 55.0`) und München (`max_explore_price_eur: 120.0`) anpassen,
- die Aufenthaltsdauer (`min_stay_days: 3`, `max_stay_days: 14`) ändern,
- oder weitere `wishlist_destinations` eintragen.

---

## 💻 Lokaler Test & VS Code MCP-Einbindung

### Lokal testen (ohne Benachrichtigungsversand)
```powershell
pip install -r requirements.txt
python -m src.run_search --dry-run
```

### Ort lokal per Befehl ausschließen
```powershell
python -m src.handle_feedback --input "/exclude TIA"
```

### Optional: Gebündelten MCP-Server in VS Code nutzen
Falls du im VS-Code-Copilot-Chat direkt fragen möchtest (*„Such mir aktuelle Flugschnäppchen ab Memmingen“* oder *„Setze London-Stansted auf die Blacklist“*), kannst du in deiner `.vscode/mcp.json` folgenden Eintrag hinzufügen:
```json
{
  "servers": {
    "flight-deal-tracker": {
      "command": "python",
      "args": ["-m", "src.mcp_server"]
    }
  }
}
```
