"""NVD/CVE API-Client für CVE-Validierung."""
import logging
import time
from pathlib import Path

print("[Startup]       nvd_client: import requests...", flush=True)
import requests
print("[Startup]       nvd_client: OK", flush=True)

from app.config import settings

logger = logging.getLogger(__name__)

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
RATE_LIMIT_DELAY = 6.5  # 5 req/30s ohne Key -> 6.5s zwischen Requests


class NVDClient:
    """Client für NVD API mit In-Memory-Cache (TTL 24h)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.nvd_api_key
        self._cache: dict[str, tuple[bool, float]] = {}  # cve_id -> (valid, timestamp)
        self._cache_ttl = 24 * 3600  # 24h
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        """Respektiert NVD Rate Limit (5/30s ohne Key, 50/30s mit Key)."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request = time.monotonic()

    def _is_cached_valid(self, cve_id: str) -> bool | None:
        """Gibt True/False wenn gecacht, sonst None."""
        if cve_id not in self._cache:
            return None
        valid, ts = self._cache[cve_id]
        if time.time() - ts > self._cache_ttl:
            del self._cache[cve_id]
            return None
        return valid

    def validate_cve(self, cve_id: str) -> bool:
        """
        Prüft ob CVE existiert und nicht withdrawn ist.
        Nutzt Cache (TTL 24h).
        """
        cve_id = (cve_id or "").strip().upper()
        if not cve_id or not cve_id.startswith("CVE-"):
            return False

        cached = self._is_cached_valid(cve_id)
        if cached is not None:
            return cached

        self._rate_limit()
        try:
            headers = {}
            if self.api_key:
                headers["apiKey"] = self.api_key

            resp = requests.get(
                f"{NVD_API_BASE}?cveId={cve_id}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            vulnerabilities = data.get("vulnerabilities", [])
            if not vulnerabilities:
                self._cache[cve_id] = (False, time.time())
                return False

            cve_data = vulnerabilities[0].get("cve", {})
            # withdrawn: CVE wurde zurückgezogen
            if cve_data.get("withdrawn"):
                self._cache[cve_id] = (False, time.time())
                return False

            self._cache[cve_id] = (True, time.time())
            return True
        except Exception as e:
            logger.warning("NVD-API-Fehler für %s: %s", cve_id, e)
            # Bei API-Fehler: CVE als ungültig markieren (konservativ)
            self._cache[cve_id] = (False, time.time())
            return False

    def validate_cves(self, cve_ids: list[str]) -> dict[str, bool]:
        """Validiert mehrere CVEs. Gibt Dict cve_id -> valid."""
        return {cve_id: self.validate_cve(cve_id) for cve_id in (cve_ids or [])}
