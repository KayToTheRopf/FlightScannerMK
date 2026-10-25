from __future__ import annotations

"""
Gebündelter MCP-Server (Model Context Protocol) für VS Code / Copilot Chat.
Statt 3 einzelner MCPs pro API stellt dieser EINE Server alle 3 Flug-Provider
(Ryanair, Travelpayouts, Google Flights) sowie die Blacklist- und Wunschlisten-Steuerung
als komfortable Chat-Tools bereit.

Für den automatischen 2x-täglich-Lauf in GitHub Actions wird dieser Server NICHT benötigt
(dort läuft direkt `python -m src.run_search`).
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.analyzer import DealAnalyzer
from src.handle_feedback import add_exclusion, add_or_update_wishlist, load_blacklist
from src.run_search import DEFAULT_BLACKLIST_PATH, DEFAULT_CONFIG_PATH, DEFAULT_HISTORY_PATH, collect_all_offers, load_config

mcp = FastMCP("FlightDealTracker")


@mcp.tool()
def search_flight_bargains(origin_filter: Optional[str] = None, max_results: int = 10) -> str:
    """
    Sucht live über alle aktivierten kostenlosen Provider (Ryanair, Travelpayouts, Google Flights)
    nach echten Flugschnäppchen ab München (MUC) und Memmingen (FMM).
    """
    config = load_config(DEFAULT_CONFIG_PATH)
    if origin_filter:
        code = origin_filter.upper().strip()
        config["departure_airports"] = [
            d for d in config.get("departure_airports", []) if d.get("code", "").upper() == code
        ]

    analyzer = DealAnalyzer(
        config=config,
        blacklist_path=DEFAULT_BLACKLIST_PATH,
        history_path=DEFAULT_HISTORY_PATH,
    )
    offers = collect_all_offers(config)
    deals = analyzer.evaluate_offers(offers)[:max_results]
    analyzer.save_history()

    if not deals:
        return "Keine neuen Schnäppchen unterhalb deiner Preisschwellen gefunden."

    lines = [f"Gefundene Schnäppchen ({len(deals)}):"]
    for d in deals:
        o = d.offer
        lines.append(
            f"- {o.origin} -> {o.destination_name} ({o.destination}, {o.destination_country}): "
            f"{o.price_eur:.2f} EUR ({o.outbound_date} bis {o.inbound_date}, {o.stay_days} Tage, {o.airline} via {o.provider}) | {d.reason}"
        )
    return "\n".join(lines)


@mcp.tool()
def exclude_destination(target: str) -> str:
    """
    Schließt einen Flughafen-Code (z.B. 'TIA'), eine Stadt ('city:Tirana') oder ein Land ('country:Albanien')
    dauerhaft in `config/blacklist.json` von der Schnäppchen-Suche aus.
    """
    _, msg = add_exclusion(target, blacklist_path=DEFAULT_BLACKLIST_PATH)
    return msg


@mcp.tool()
def upsert_wishlist_destination(iata_code: str, max_price_eur: float, city_name: Optional[str] = None) -> str:
    """
    Fügt ein neues Wunschziel mit Maximalpreis (Hin & Zurück in EUR) zu `config/search_config.yaml` hinzu
    oder aktualisiert den Zielpreis.
    """
    _, msg = add_or_update_wishlist(iata_code, max_price_eur, name=city_name, config_path=DEFAULT_CONFIG_PATH)
    return msg


@mcp.tool()
def show_current_blacklist() -> dict:
    """Zeigt alle aktuell ausgeschlossenen Flughäfen, Städte und Länder aus `config/blacklist.json`."""
    return load_blacklist(DEFAULT_BLACKLIST_PATH)


if __name__ == "__main__":
    mcp.run()
