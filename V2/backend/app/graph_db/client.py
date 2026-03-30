"""Neo4j Graph-Client."""
from neo4j import AsyncGraphDatabase
from app.config import settings
from app.schemas.graph import TacticInfo, TechniqueInfo


class GraphClient:
    """Asynchroner Neo4j-Client für den Reasoning Graph."""

    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    async def close(self):
        """Schließt die Verbindung."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def verify_connectivity(self) -> bool:
        """Prüft die Verbindung zu Neo4j."""
        try:
            driver = self._get_driver()
            await driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def get_tactics(self) -> list[TacticInfo]:
        """Gibt alle Taktiken zurück."""
        from app.graph_db import queries

        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(queries.GET_TACTICS)
            records = await result.data()
            if records:
                return [TacticInfo(id=r["id"], name=r["name"], short_name=r["short_name"]) for r in records]

        # Fallback: Standard MITRE ATT&CK Taktiken wenn Graph leer
        return self._get_default_tactics()

    def _get_default_tactics(self) -> list[TacticInfo]:
        """Fallback-Taktiken wenn Neo4j leer ist."""
        defaults = [
            ("initial-access", "Initial Access", "INI"),
            ("execution", "Execution", "EXE"),
            ("persistence", "Persistence", "PERS"),
            ("privilege-escalation", "Privilege Escalation", "PE"),
            ("defense-evasion", "Defense Evasion", "DE"),
            ("credential-access", "Credential Access", "CA"),
            ("discovery", "Discovery", "DISC"),
            ("lateral-movement", "Lateral Movement", "LM"),
            ("collection", "Collection", "COLL"),
            ("command-and-control", "Command and Control", "C2"),
            ("exfiltration", "Exfiltration", "EXF"),
            ("impact", "Impact", "IMP"),
        ]
        return [TacticInfo(id=id_, name=name, short_name=short) for id_, name, short in defaults]

    async def get_techniques(self) -> list[TechniqueInfo]:
        """Gibt alle Techniken zurück."""
        from app.graph_db import queries

        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(queries.GET_TECHNIQUES)
            records = await result.data()
            if records:
                return [
                    TechniqueInfo(id=r["id"], name=r["name"], tactic_ids=r.get("tactic_ids", []))
                    for r in records
                ]

        return []

    async def validate_tactic_sequence(
        self, tactic_ids: list[str], order_override: list[str] | None = None
    ) -> dict:
        """Validiert eine Taktik-Sequenz auf kausale Korrektheit."""
        if not tactic_ids:
            return {"valid": True, "message": "Leere Sequenz"}

        from app.graph_db.queries import TACTIC_ORDER

        order_list = order_override if order_override is not None else TACTIC_ORDER
        order_map = {t: i for i, t in enumerate(order_list)}
        last_idx = -1
        for tid in tactic_ids:
            normalized = tid.lower().replace(" ", "-")
            idx = order_map.get(normalized, -1)
            if idx == -1:
                return {"valid": False, "message": f"Unbekannte Taktik: {tid}"}
            if idx < last_idx:
                return {
                    "valid": False,
                    "message": f"Kausale Reihenfolge verletzt: {tid} nach vorheriger Taktik",
                }
            last_idx = idx

        return {"valid": True, "message": "Sequenz gültig"}


_graph_client: GraphClient | None = None


def get_graph_client() -> GraphClient:
    """Singleton-Zugriff auf den Graph-Client."""
    global _graph_client
    if _graph_client is None:
        _graph_client = GraphClient()
    return _graph_client
