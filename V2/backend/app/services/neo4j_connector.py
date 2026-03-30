"""Neo4j Connector Service für Attack-Path-Validierung.

Neo4j-Import ist lazy: GraphDatabase wird erst bei _get_driver() geladen.
Verhindert 5+ Min Hänger beim App-Start (neo4j-Paket blockiert sonst).
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Cypher-Queries (HAS_TECHNIQUE: Tactic -> Technique, siehe seed_mitre.py)
QUERY_START_TECHNIQUE = """
MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(t:Technique {id: $tgt})
WHERE tac.id IN ['reconnaissance', 'initial-access']
RETURN t LIMIT 1
"""

QUERY_PATH = """
MATCH p=shortestPath((a:Technique {id: $src})-[:PRECEDES*]->(b:Technique {id: $tgt}))
RETURN p
"""

QUERY_TECHNIQUE_DETAILS = """
MATCH (t:Technique {id: $tech_id})
RETURN t.name AS name, t.description AS description
"""

QUERY_TECHNIQUE_EXISTS = """
MATCH (t:Technique {id: $tech_id})
RETURN t LIMIT 1
"""

QUERY_TECHNIQUE_TACTICS = """
MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(t:Technique {id: $tech_id})
RETURN tac.id AS tactic_id
"""

QUERY_ALL_TECHNIQUES = """
MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(tech:Technique)
WITH tech, collect(tac.id) AS tactic_ids
RETURN tech.id AS id, tech.name AS name, tech.description AS description, tactic_ids
ORDER BY tech.id
"""

# Deterministischer Fallback – alternative Techniken von source aus erreichbar
QUERY_ALTERNATIVE_TECHNIQUES = """
MATCH (a:Technique {id: $src})-[:PRECEDES*1..4]->(b:Technique)
WHERE b.id <> $exclude
RETURN DISTINCT b.id AS id
LIMIT 5
"""

# Start-Techniken (Phase "in"): Reconnaissance, Initial Access
QUERY_START_ALTERNATIVES = """
MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(t:Technique)
WHERE tac.id IN ['reconnaissance', 'initial-access', 'resource-development']
RETURN t.id AS id
LIMIT 10
"""

# Akteursspezifische Techniken (Group USES_TECHNIQUE)
QUERY_TECHNIQUES_FOR_GROUP = """
MATCH (g:Group)-[:USES_TECHNIQUE]->(t:Technique)
WHERE g.name = $name
   OR (g.aliases IS NOT NULL AND $name IN [x IN split(g.aliases, ',') | trim(x)])
OPTIONAL MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(t)
RETURN t.id AS id, t.name AS name, tac.id AS tactic
ORDER BY tac.id, t.id
"""


class Neo4jService:
    """Singleton-Service für Neo4j-Verbindung und Attack-Path-Validierung."""

    _instance: "Neo4jService | None" = None

    def __new__(cls) -> "Neo4jService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._driver = None
        self._initialized = True

    def _get_driver(self):
        """Lazy-Initialisierung des Neo4j-Drivers (Import erst hier, nicht beim App-Start)."""
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=15,
            )
            logger.info("Neo4j: Verbindung hergestellt, URI=%s", settings.neo4j_uri)
        return self._driver

    def close(self) -> None:
        """Schließt die Neo4j-Verbindung."""
        if self._driver:
            try:
                self._driver.close()
            except Exception as e:
                logger.error("Fehler beim Schließen der Neo4j-Verbindung: %s", e)
            finally:
                self._driver = None

    def verify_connectivity(self) -> bool:
        """Prüft die Verbindung zu Neo4j."""
        try:
            driver = self._get_driver()
            driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Neo4j-Verbindungsprüfung fehlgeschlagen: %s", e, exc_info=True)
            return False

    def validate_path(
        self,
        source_tech_id: str | None,
        target_tech_id: str,
    ) -> bool:
        """
        Prüft, ob ein gültiger Attack-Path zwischen den Techniken existiert.

        - Bei source_tech_id=None (Start): Prüft, ob target_tech_id in
          Reconnaissance oder Initial Access liegt.
        - Sonst: Prüft, ob ein PRECEDES-Pfad von source zu target existiert.
        """
        if source_tech_id == target_tech_id:
            return True

        try:
            driver = self._get_driver()
            with driver.session() as session:
                if source_tech_id is None:
                    result = session.run(
                        QUERY_START_TECHNIQUE,
                        tgt=target_tech_id,
                    )
                else:
                    result = session.run(
                        QUERY_PATH,
                        src=source_tech_id,
                        tgt=target_tech_id,
                    )
                records = list(result)
                return len(records) > 0
        except Exception as e:
            logger.error(
                "Neo4j-Fehler bei validate_path(%r, %r): %s",
                source_tech_id,
                target_tech_id,
                e,
                exc_info=True,
            )
            return False

    def technique_exists(self, tech_id: str) -> bool:
        """Prüft ob Technik-ID im KG existiert (DR1 TTP-Konformität)."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(QUERY_TECHNIQUE_EXISTS, tech_id=tech_id)
                return result.single() is not None
        except Exception as e:
            logger.error("Neo4j technique_exists(%r): %s", tech_id, e)
            return False

    def get_technique_tactics(self, tech_id: str) -> list[str]:
        """Liefert Taktik-IDs für eine Technik (für Phasenprüfung)."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(QUERY_TECHNIQUE_TACTICS, tech_id=tech_id)
                return [r["tactic_id"] for r in result if r.get("tactic_id")]
        except Exception as e:
            logger.error("Neo4j get_technique_tactics(%r): %s", tech_id, e)
            return []

    def get_all_techniques(self) -> list[dict]:
        """Liefert alle Techniken mit Taktik-Zuordnung für RAG/Generator-Kontext."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(QUERY_ALL_TECHNIQUES)
                return [
                    {
                        "id": r["id"],
                        "name": r["name"] or "",
                        "description": r["description"] or "",
                        "tactic_ids": r.get("tactic_ids") or [],
                    }
                    for r in result
                ]
        except Exception as e:
            logger.error("Neo4j get_all_techniques: %s", e)
            return []

    def get_alternative_techniques(
        self,
        source_tech_id: str | None,
        exclude_tech_id: str | None = None,
    ) -> list[str]:
        """
        Deterministischer Fallback. Liefert alternative Technik-IDs,
        die von source aus über PRECEDES erreichbar sind.
        Bei source=None: Start-Techniken (Phase in).
        """
        try:
            driver = self._get_driver()
            with driver.session() as session:
                if source_tech_id is None:
                    result = session.run(QUERY_START_ALTERNATIVES)
                else:
                    result = session.run(
                        QUERY_ALTERNATIVE_TECHNIQUES,
                        src=source_tech_id,
                        exclude=exclude_tech_id or "",
                    )
                ids = [r["id"] for r in result if r.get("id")]
                return ids[:5]
        except Exception as e:
            logger.error(
                "Neo4j get_alternative_techniques(%r, %r): %s",
                source_tech_id,
                exclude_tech_id,
                e,
            )
            return []

    def get_technique_details(self, tech_id: str) -> dict:
        """
        Holt Name und Beschreibung für eine Technik-ID.

        Returns:
            {"name": "...", "description": "..."} wenn gefunden, sonst {}.
        """
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(QUERY_TECHNIQUE_DETAILS, tech_id=tech_id)
                record = result.single()
                if record:
                    return {
                        "name": record["name"] or "",
                        "description": record["description"] or "",
                    }
                return {}
        except Exception as e:
            logger.error(
                "Neo4j-Fehler bei get_technique_details(%r): %s",
                tech_id,
                e,
                exc_info=True,
            )
            return {}

    def get_techniques_for_group(self, threat_actor: str) -> list[dict]:
        """
        Liefert Techniken, die ein Bedrohungsakteur (Group) historisch nutzt.

        Returns:
            [{"id": "T1566.001", "name": "...", "tactic": "initial-access"}, ...]
            Leere Liste wenn Akteur nicht im KG existiert.
        """
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(
                    QUERY_TECHNIQUES_FOR_GROUP,
                    name=threat_actor,
                )
                return [
                    {
                        "id": r["id"],
                        "name": r["name"] or "",
                        "tactic": r["tactic"],
                    }
                    for r in result
                    if r.get("id")
                ]
        except Exception as e:
            logger.debug("get_techniques_for_group(%r): %s", threat_actor, e)
            return []


def get_neo4j_service() -> Neo4jService:
    """Singleton-Zugriff auf den Neo4j-Service."""
    return Neo4jService()
