"""Unit Tests für NVD/CVE Client (mit Mock)."""
import pytest
from unittest.mock import patch, MagicMock

from app.rag.nvd_client import NVDClient


class TestNVDClientValidateCVE:
    def test_validate_cve_invalid_format(self):
        """'xyz', '', 'T1566' → False (kein CVE-Format)."""
        client = NVDClient()
        assert client.validate_cve("xyz") is False
        assert client.validate_cve("") is False
        assert client.validate_cve("T1566") is False

    def test_validate_cve_cache_hit(self):
        """Zweiter Aufruf nutzt Cache, kein API-Call."""
        client = NVDClient()
        with patch("app.rag.nvd_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "vulnerabilities": [{"cve": {"id": "CVE-2024-1234"}}],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            r1 = client.validate_cve("CVE-2024-1234")
            r2 = client.validate_cve("CVE-2024-1234")

            assert r1 is True
            assert r2 is True
            assert mock_get.call_count == 1

    def test_validate_cve_mock_api_valid(self):
        """Mock: CVE-2024-1234 existiert → True."""
        client = NVDClient()
        with patch("app.rag.nvd_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "vulnerabilities": [
                    {"cve": {"id": "CVE-2024-1234", "withdrawn": None}},
                ],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            assert client.validate_cve("CVE-2024-1234") is True

    def test_validate_cve_mock_api_withdrawn(self):
        """Mock: withdrawn=True → False."""
        client = NVDClient()
        with patch("app.rag.nvd_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "vulnerabilities": [
                    {"cve": {"id": "CVE-2024-1234", "withdrawn": "2024-01-01"}},
                ],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            assert client.validate_cve("CVE-2024-1234") is False

    def test_validate_cve_mock_api_empty_vulnerabilities(self):
        """Mock: leere vulnerabilities → False."""
        client = NVDClient()
        with patch("app.rag.nvd_client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"vulnerabilities": []}
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            assert client.validate_cve("CVE-2024-9999") is False
