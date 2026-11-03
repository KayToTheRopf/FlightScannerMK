from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_FLIGHT_CONFIG: Dict[str, Any] = {
    "departure_airports": [
        {"code": "FMM", "name": "Memmingen", "max_explore_price_eur": 55.0},
        {"code": "MUC", "name": "München", "max_explore_price_eur": 120.0},
    ],
    "search_window": {
        "months_ahead": 6,
        "min_stay_days": 3,
        "max_stay_days": 14,
        "adults": 1,
        "currency": "EUR",
        "max_stops": 1,
    },
    "deal_scoring": {
        "min_discount_vs_history_percent": 25.0,
        "first_seen_margin_percent": 10.0,
        "notification_cooldown_days": 7,
        "max_deals_per_run": 10,
    },
    "wishlist_destinations": [
        {"code": "PMI", "name": "Palma de Mallorca", "country": "Spanien", "max_price_eur": 65.0},
        {"code": "LIS", "name": "Lissabon", "country": "Portugal", "max_price_eur": 115.0},
        {"code": "BCN", "name": "Barcelona", "country": "Spanien", "max_price_eur": 85.0},
        {"code": "ROM", "name": "Rom (FCO/CIA)", "country": "Italien", "airports": ["FCO", "CIA"], "max_price_eur": 70.0},
        {"code": "ATH", "name": "Athen", "country": "Griechenland", "max_price_eur": 95.0},
        {"code": "TFS", "name": "Teneriffa Süd", "country": "Spanien", "max_price_eur": 110.0},
    ],
    "providers": {
        "ryanair": {"enabled": True},
        "travelpayouts": {"enabled": True, "verify_with_google_flights": True},
        "google_flights": {"enabled": True, "sample_dates_per_wishlist": 3},
    },
    "notifications": {
        "discord": {"enabled": True},
        "github_issue": {"enabled": True, "issue_label": "flight-deal"},
        "email": {"enabled": False},
    },
}


class _FallbackResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        return json.loads(self.text)


class _FallbackSession:
    def __init__(self) -> None:
        self.headers: Dict[str, str] = {}

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 20,
    ) -> _FallbackResponse:
        full_url = url
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            full_url = f"{url}?{qs}"
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(full_url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _FallbackResponse(resp.status, resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return _FallbackResponse(exc.code, body)


class _FallbackRequestsModule:
    Session = _FallbackSession

    @staticmethod
    def get(
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 20,
    ) -> _FallbackResponse:
        return _FallbackSession().get(url, params=params, headers=headers, timeout=timeout)

    @staticmethod
    def _request(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_payload: Any = None,
        timeout: int = 15,
    ) -> _FallbackResponse:
        req_headers = dict(headers or {})
        data = None
        if json_payload is not None:
            data = json.dumps(json_payload).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _FallbackResponse(resp.status, resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return _FallbackResponse(exc.code, body)

    @classmethod
    def post(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
        timeout: int = 15,
    ) -> _FallbackResponse:
        return cls._request("POST", url, headers=headers, json_payload=json, timeout=timeout)

    @classmethod
    def patch(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
        timeout: int = 15,
    ) -> _FallbackResponse:
        return cls._request("PATCH", url, headers=headers, json_payload=json, timeout=timeout)


class _FallbackYamlModule:
    @staticmethod
    def safe_load(stream: Any) -> Dict[str, Any]:
        import re

        raw = stream.read() if hasattr(stream, "read") else str(stream)
        raw_str = raw.strip()
        if not raw_str:
            return {}
        try:
            return json.loads(raw_str)
        except Exception:
            pass

        cfg: Dict[str, Any] = json.loads(json.dumps(DEFAULT_FLIGHT_CONFIG))

        m_pause = re.search(r'^\s*pause_until\s*:\s*["\']?([^"\'\n#]*)["\']?', raw_str, flags=re.MULTILINE)
        if m_pause:
            cfg["pause_until"] = m_pause.group(1).strip()

        m_force = re.search(r'^\s*force_next_discord\s*:\s*(true|false)', raw_str, flags=re.MULTILINE | re.IGNORECASE)
        if m_force:
            cfg["force_next_discord"] = m_force.group(1).strip().lower() == "true"

        # Parse wishlist_destinations block if present
        m_wish_sec = re.search(
            r"^wishlist_destinations\s*:\s*\n((?:^[ \t]+.*\n?)*)",
            raw_str,
            flags=re.MULTILINE,
        )
        if m_wish_sec:
            block = m_wish_sec.group(1)
            items = []
            current: Dict[str, Any] = {}
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("- "):
                    if current:
                        items.append(current)
                    current = {}
                    stripped = stripped[2:].strip()
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = re.sub(r"\s+#.*$", "", v).strip()
                    if v.startswith("[") and v.endswith("]"):
                        try:
                            current[k] = json.loads(v)
                        except Exception:
                            current[k] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
                    else:
                        v_clean = v.strip("\"'")
                        if k in ("max_price_eur", "max_explore_price_eur"):
                            try:
                                current[k] = float(v_clean)
                            except ValueError:
                                current[k] = v_clean
                        else:
                            current[k] = v_clean
            if current:
                items.append(current)
            if items or "[]" in m_wish_sec.group(0):
                cfg["wishlist_destinations"] = items

        return cfg

    @staticmethod
    def safe_dump(data: Any, stream: Any = None, **kwargs: Any) -> str:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if stream is not None and hasattr(stream, "write"):
            stream.write(text)
        return text



try:
    import requests as requests_mod  # type: ignore
except ImportError:
    requests_mod = _FallbackRequestsModule()  # type: ignore

try:
    import yaml as yaml_mod  # type: ignore
except ImportError:
    yaml_mod = _FallbackYamlModule()  # type: ignore
