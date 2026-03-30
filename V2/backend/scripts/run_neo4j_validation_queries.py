#!/usr/bin/env python3
"""
Validierung des Knowledge Graphs: Führt die 5 Cypher-Queries aus dem
NS-MAS Validierungsplan aus.

Erwartung:
- Tactic-Knoten = 14, Technique-Knoten > 200 (oder 43 bei Fallback)
- Group-Knoten > 0, PRECEDES-Kanten > 0
- T1566.001 existiert, Lazarus-Group-Techniken vorhanden
- PRECEDES-Pfad T1566.001 → T1570 existiert

Usage: python -m scripts.run_neo4j_validation_queries
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.neo4j_connector import Neo4jService


def _neo4j_port_reachable() -> bool:
    """Schneller Port-Check (1s) bevor Neo4j-Driver geladen wird."""
    import socket
    from urllib.parse import urlparse
    from app.config import settings
    uri = settings.neo4j_uri
    try:
        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 7688
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


def run_queries():
    if not _neo4j_port_reachable():
        print("FEHLER: Neo4j nicht erreichbar (Port 7688).")
        print("  Starte Neo4j und führe ggf. python -m scripts.seed_mitre aus.")
        return 1

    neo4j = Neo4jService()
    driver = neo4j._get_driver()

    if not neo4j.verify_connectivity():
        print("FEHLER: Keine Verbindung zu Neo4j. Prüfe URI und Credentials.")
        return 1

    print("=" * 60)
    print("Neo4j Knowledge Graph – Validierungsqueries")
    print("=" * 60)

    with driver.session() as session:
        # 1. Knoten pro Typ
        print("\n1. Knoten pro Typ:")
        result = session.run(
            "MATCH (n) RETURN labels(n) AS type, count(n) AS count"
        )
        for r in result:
            labels = r["type"]
            count = r["count"]
            label_str = ":".join(labels) if labels else "(unlabeled)"
            print(f"   {label_str}: {count}")

        # 2. PRECEDES-Kanten
        print("\n2. PRECEDES-Kanten zwischen Techniken:")
        result = session.run(
            "MATCH ()-[r:PRECEDES]->() RETURN count(r) AS precedes_count"
        )
        rec = result.single()
        precedes_count = rec["precedes_count"] if rec else 0
        print(f"   count: {precedes_count}")

        # 3. T1566.001 existiert?
        print("\n3. Technik T1566.001 existiert im Graph:")
        result = session.run(
            "MATCH (t:Technique {id: $tech_id}) RETURN t.id AS id, t.name AS name",
            tech_id="T1566.001",
        )
        rec = result.single()
        if rec:
            print(f"   JA: id={rec['id']}, name={rec['name']}")
        else:
            print("   NEIN (nicht gefunden)")

        # 4. Lazarus Group Techniken (nutzt gleiche Logik wie neo4j_connector)
        print("\n4. Techniken für Lazarus Group:")
        result = session.run(
            """
            MATCH (g:Group)-[:USES_TECHNIQUE]->(t:Technique)
            WHERE g.name = $name
               OR (g.aliases IS NOT NULL AND $name IN [x IN split(g.aliases, ',') | trim(x)])
            RETURN t.id AS id, t.name AS name
            ORDER BY t.id
            LIMIT 10
            """,
            name="Lazarus Group",
        )
        rows = list(result)
        if rows:
            for r in rows:
                print(f"   {r['id']}: {r['name']}")
        else:
            print("   Keine gefunden (Group möglicherweise nicht im Graph)")

        # 5. PRECEDES-Pfad T1566.001 → T1570
        print("\n5. PRECEDES-Pfad von T1566.001 zu T1570:")
        result = session.run(
            """
            MATCH p=shortestPath((a:Technique {id: $src})-[:PRECEDES*]->(b:Technique {id: $tgt}))
            RETURN length(p) AS path_length
            """,
            src="T1566.001",
            tgt="T1570",
        )
        rec = result.single()
        if rec is not None:
            print(f"   Pfadlänge: {rec['path_length']}")
        else:
            # Fallback: Prüfe mit Basis-ID T1566
            result2 = session.run(
                """
                MATCH p=shortestPath((a:Technique {id: $src})-[:PRECEDES*]->(b:Technique {id: $tgt}))
                RETURN length(p) AS path_length
                """,
                src="T1566",
                tgt="T1570",
            )
            rec2 = result2.single()
            if rec2 is not None:
                print(f"   T1566.001 nicht gefunden; T1566→T1570 Pfadlänge: {rec2['path_length']}")
            else:
                print("   Kein Pfad gefunden")

    print("\n" + "=" * 60)
    print("Validierung abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(run_queries())
