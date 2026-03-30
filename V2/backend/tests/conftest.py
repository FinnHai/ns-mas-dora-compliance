"""Pytest-Konfiguration und Fixtures."""
import os
import platform
import sys

# Workaround: platform vor Thread-Pools cachen (Apple Silicon pytest-Hang)
_ = platform.system()
_ = platform.node()
_ = platform.platform()
_ = platform.python_version()
_ = platform.machine()

# Neo4j mocken für Unit-Tests (verhindert Hang auf macOS) – nur wenn MOCK_NEO4J=1
if os.environ.get("MOCK_NEO4J") == "1":
    from unittest.mock import MagicMock
    _mock_neo4j = MagicMock()
    _mock_neo4j.GraphDatabase = MagicMock()
    sys.modules["neo4j"] = _mock_neo4j

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Async HTTP-Client für API-Tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
