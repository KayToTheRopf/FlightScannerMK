from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Dict, List, Tuple

from src.models import FlightOffer

# Häufige IATA-Codes für lesbare Städtenamen, falls die API nur den Code liefert
IATA_CITY_MAP: Dict[str, Tuple[str, str]] = {
    "MUC": ("München", "Deutschland"),
    "FMM": ("Memmingen", "Deutschland"),
    "PMI": ("Palma de Mallorca", "Spanien"),
    "BCN": ("Barcelona", "Spanien"),
    "MAD": ("Madrid", "Spanien"),
    "AGP": ("Málaga", "Spanien"),
    "ALC": ("Alicante", "Spanien"),
    "VLC": ("Valencia", "Spanien"),
    "TFS": ("Teneriffa Süd", "Spanien"),
    "LPA": ("Gran Canaria", "Spanien"),
    "ACE": ("Lanzarote", "Spanien"),
    "FUE": ("Fuerteventura", "Spanien"),
    "IBZ": ("Ibiza", "Spanien"),
    "SVQ": ("Sevilla", "Spanien"),
    "LIS": ("Lissabon", "Portugal"),
    "OPO": ("Porto", "Portugal"),
    "FAO": ("Faro", "Portugal"),
    "FNC": ("Madeira (Funchal)", "Portugal"),
    "FCO": ("Rom-Fiumicino", "Italien"),
    "CIA": ("Rom-Ciampino", "Italien"),
    "MXP": ("Mailand-Malpensa", "Italien"),
    "BGY": ("Mailand-Bergamo", "Italien"),
    "NAP": ("Neapel", "Italien"),
    "CTA": ("Catania (Sizilien)", "Italien"),
    "PMO": ("Palermo (Sizilien)", "Italien"),
    "BRI": ("Bari", "Italien"),
    "BDS": ("Brindisi", "Italien"),
    "PSA": ("Pisa", "Italien"),
    "BLQ": ("Bologna", "Italien"),
    "VCE": ("Venedig", "Italien"),
    "CAG": ("Cagliari (Sardinien)", "Italien"),
    "AHO": ("Alghero (Sardinien)", "Italien"),
    "ATH": ("Athen", "Griechenland"),
    "SKG": ("Thessaloniki", "Griechenland"),
    "HER": ("Heraklion (Kreta)", "Griechenland"),
    "CHQ": ("Chania (Kreta)", "Griechenland"),
    "RHO": ("Rhodos", "Griechenland"),
    "CFU": ("Korfu", "Griechenland"),
    "KGS": ("Kos", "Griechenland"),
    "ZTH": ("Zakynthos", "Griechenland"),
    "JTR": ("Santorini", "Griechenland"),
    "ZAD": ("Zadar", "Kroatien"),
    "SPU": ("Split", "Kroatien"),
    "DBV": ("Dubrovnik", "Kroatien"),
    "PUY": ("Pula", "Kroatien"),
    "ZAG": ("Zagreb", "Kroatien"),
    "RJK": ("Rijeka", "Kroatien"),
    "TIA": ("Tirana", "Albanien"),
    "SOF": ("Sofia", "Bulgarien"),
    "VAR": ("Varna", "Bulgarien"),
    "BOJ": ("Burgas", "Bulgarien"),
    "OTP": ("Bukarest", "Rumänien"),
    "CLJ": ("Cluj-Napoca", "Rumänien"),
    "SBZ": ("Sibiu", "Rumänien"),
    "TSR": ("Timișoara", "Rumänien"),
    "BEG": ("Belgrad", "Serbien"),
    "INI": ("Niš", "Serbien"),
    "SJJ": ("Sarajevo", "Bosnien und Herzegowina"),
    "BNX": ("Banja Luka", "Bosnien und Herzegowina"),
    "TGD": ("Podgorica", "Montenegro"),
    "TIV": ("Tivat", "Montenegro"),
    "SKP": ("Skopje", "Nordmazedonien"),
    "OHD": ("Ohrid", "Nordmazedonien"),
    "PRN": ("Pristina", "Kosovo"),
    "LCA": ("Larnaka", "Zypern"),
    "PFO": ("Paphos", "Zypern"),
    "MLA": ("Malta", "Malta"),
    "DUB": ("Dublin", "Irland"),
    "STN": ("London-Stansted", "Vereinigtes Königreich"),
    "LGW": ("London-Gatwick", "Vereinigtes Königreich"),
    "LHR": ("London-Heathrow", "Vereinigtes Königreich"),
    "MAN": ("Manchester", "Vereinigtes Königreich"),
    "EDI": ("Edinburgh", "Vereinigtes Königreich"),
    "CDG": ("Paris-CDG", "Frankreich"),
    "ORY": ("Paris-Orly", "Frankreich"),
    "NCE": ("Nizza", "Frankreich"),
    "MRS": ("Marseille", "Frankreich"),
    "AMS": ("Amsterdam", "Niederlande"),
    "EIN": ("Eindhoven", "Niederlande"),
    "BRU": ("Brüssel", "Belgien"),
    "CPH": ("Kopenhagen", "Dänemark"),
    "ARN": ("Stockholm", "Schweden"),
    "OSL": ("Oslo", "Norwegen"),
    "HEL": ("Helsinki", "Finnland"),
    "RIX": ("Riga", "Lettland"),
    "VNO": ("Vilnius", "Litauen"),
    "TLL": ("Tallinn", "Estland"),
    "KRK": ("Krakau", "Polen"),
    "GDN": ("Danzig", "Polen"),
    "WAW": ("Warschau", "Polen"),
    "BUD": ("Budapest", "Ungarn"),
    "PRG": ("Prag", "Tschechien"),
    "VIE": ("Wien", "Österreich"),
    "ZRH": ("Zürich", "Schweiz"),
    "IST": ("Istanbul", "Türkei"),
    "SAW": ("Istanbul-Sabiha Gökçen", "Türkei"),
    "AYT": ("Antalya", "Türkei"),
    "ADB": ("Izmir", "Türkei"),
    "RAK": ("Marrakesch", "Marokko"),
    "AGA": ("Agadir", "Marokko"),
    "TNG": ("Tanger", "Marokko"),
    "FEZ": ("Fès", "Marokko"),
    "AMM": ("Amman", "Jordanien"),
    "TLV": ("Tel Aviv", "Israel"),
    "DXB": ("Dubai", "Vereinigte Arabische Emirate"),
    "AUH": ("Abu Dhabi", "Vereinigte Arabische Emirate"),
    "JFK": ("New York (JFK)", "USA"),
    "EWR": ("New York (Newark)", "USA"),
    "BOS": ("Boston", "USA"),
    "MIA": ("Miami", "USA"),
    "LAX": ("Los Angeles", "USA"),
    "SFO": ("San Francisco", "USA"),
    "BKK": ("Bangkok", "Thailand"),
    "SIN": ("Singapur", "Singapur"),
    "NRT": ("Tokio-Narita", "Japan"),
    "HND": ("Tokio-Haneda", "Japan"),
}


def resolve_city_and_country(iata: str, fallback_city: str = "", fallback_country: str = "") -> Tuple[str, str]:
    code = (iata or "").upper().strip()
    if code in IATA_CITY_MAP:
        city, country = IATA_CITY_MAP[code]
        return fallback_city or city, fallback_country or country
    return fallback_city or code, fallback_country or "Unbekannt"


def build_google_flights_url(origin: str, destination: str, outbound_date: str, inbound_date: str) -> str:
    """Erzeugt einen direkten Google Flights Suchlink für die gegebene Verbindung."""
    q = f"Flights from {origin.upper()} to {destination.upper()} on {outbound_date[:10]} through {inbound_date[:10]}"
    from urllib.parse import quote
    return f"https://www.google.com/travel/flights?hl=de&curr=EUR&q={quote(q)}"


def date_window(months_ahead: int = 6) -> Tuple[date, date]:
    start = date.today() + timedelta(days=3)
    end = date.today() + timedelta(days=max(30, months_ahead * 30))
    return start, end


class FlightProvider(ABC):
    """Abstrakte Basisklasse für alle Flugpreis-Provider."""

    name: str = "base"

    @abstractmethod
    def search_deals(self, config: dict) -> List[FlightOffer]:
        """Sucht nach Hin- und Rückflug-Angeboten gemäß Konfiguration."""
        raise NotImplementedError
