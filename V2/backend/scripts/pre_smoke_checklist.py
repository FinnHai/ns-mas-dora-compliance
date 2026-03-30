#!/usr/bin/env python3
"""
Pre-Smoke-Test-Checkliste: Prüft automatisch, ob alle Voraussetzungen erfüllt sind.

Prüft:
- .env mit OPENAI_API_KEY
- Neo4j erreichbar (Port aus NEO4J_URI)
- Backend Health-Endpoint (http://127.0.0.1:8000/health)

Usage: python -m scripts.pre_smoke_checklist
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _check_env() -> tuple[bool, str]:
    """Prüft .env und OPENAI_API_KEY."""
    from app.config import settings
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return False, f".env nicht gefunden: {env_path}"
    key = (settings.openai_api_key or "").strip()
    if not key or not key.startswith("sk-"):
        return False, "OPENAI_API_KEY fehlt oder ungültig in .env"
    return True, f"OPENAI_API_KEY gesetzt (Länge {len(key)})"


def _check_neo4j() -> tuple[bool, str]:
    """Prüft ob Neo4j-Port erreichbar ist."""
    from app.config import settings
    uri = settings.neo4j_uri
    try:
        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 7688
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        return True, f"Neo4j erreichbar ({host}:{port})"
    except Exception as e:
        return False, f"Neo4j nicht erreichbar: {e}"


def _check_backend() -> tuple[bool, str]:
    """Prüft Backend Health-Endpoint."""
    api_url = os.environ.get("API_URL", "http://127.0.0.1:8000")
    health_url = f"{api_url.rstrip('/')}/health"
    try:
        import urllib.request
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=5) as r:
            if r.status == 200:
                return True, f"Backend OK ({health_url})"
            return False, f"Backend HTTP {r.status}: {health_url}"
    except Exception as e:
        return False, f"Backend nicht erreichbar: {e}"


def main() -> int:
    print("=" * 60)
    print("NS-MAS Smoke Test – Pre-Checkliste")
    print("=" * 60)

    checks = [
        ("1. .env / OPENAI_API_KEY", _check_env),
        ("2. Neo4j", _check_neo4j),
        ("3. Backend Health", _check_backend),
    ]

    all_ok = True
    for name, fn in checks:
        ok, msg = fn()
        status = "✓" if ok else "✗"
        print(f"  {status} {name}: {msg}")
        if not ok:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("Alle Checks bestanden. Smoke Test kann gestartet werden:")
        print("  python -m scripts.run_smoke_test_all")
        return 0
    print("Einige Checks fehlgeschlagen. Bitte beheben vor dem Smoke Test.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
