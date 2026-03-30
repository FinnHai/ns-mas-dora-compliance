"""Cypher-Queries für den Reasoning Graph."""

GET_TACTICS = """
MATCH (t:Tactic)
RETURN t.id AS id, t.name AS name, t.short_name AS short_name
ORDER BY t.id
"""

GET_TECHNIQUES = """
MATCH (t:Tactic)-[:HAS_TECHNIQUE]->(tech:Technique)
WITH tech, collect(t.id) AS tactic_ids
RETURN tech.id AS id, tech.name AS name, tactic_ids
ORDER BY tech.id
"""

VALIDATE_TACTIC_SEQUENCE = """
UNWIND $tactic_ids AS idx
WITH idx, range(0, size($tactic_ids) - 1) AS indices
UNWIND indices AS i
WITH collect($tactic_ids[i]) AS seq
RETURN seq
"""

# Prüft, ob Taktik B nach Taktik A kausal möglich ist (PRECEDES-Relation)
CHECK_PRECEDES = """
MATCH (a:Tactic {id: $from_id})-[:PRECEDES*]->(b:Tactic {id: $to_id})
RETURN count(*) > 0 AS valid
"""

# Fallback: Wenn keine PRECEDES-Relation existiert, prüfen wir die Standard-Kill-Chain-Reihenfolge
# MITRE ATT&CK Kill Chain: Recon -> Resource Dev -> Initial Access -> Execution -> ... -> Impact
TACTIC_ORDER = [
    "reconnaissance",
    "resource-development",
    "initial-access",
    "execution",
    "persistence",
    "privilege-escalation",
    "defense-evasion",
    "credential-access",
    "discovery",
    "lateral-movement",
    "collection",
    "command-and-control",
    "exfiltration",
    "impact",
]
