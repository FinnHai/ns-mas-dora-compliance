#!/usr/bin/env python3
"""
Lädt MITRE ATT&CK Enterprise Daten in Neo4j.

- Versucht STIX 2.1 JSON von mitre/cti herunterzuladen
- Erstellt Tactic-Nodes (id, name, short_name)
- Erstellt Technique-Nodes (id, name, description)
- Verbindet (Tactic)-[:HAS_TECHNIQUE]->(Technique)
- Erstellt PRECEDES-Kanten zwischen Techniken basierend auf Kill-Chain-Reihenfolge
- Erstellt PRECEDES-Kanten zwischen Taktiken für Taktik-Sequenz-Validierung
- Bei fehlender Internetverbindung: Fallback auf repräsentative Defaults
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "dora-local-password")

MITRE_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

KILL_CHAIN_PHASES = [
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

# Tactic metadata: slug -> (display name, short_name)
TACTIC_META = {
    "reconnaissance": ("Reconnaissance", "REC"),
    "resource-development": ("Resource Development", "RD"),
    "initial-access": ("Initial Access", "INI"),
    "execution": ("Execution", "EXE"),
    "persistence": ("Persistence", "PERS"),
    "privilege-escalation": ("Privilege Escalation", "PE"),
    "defense-evasion": ("Defense Evasion", "DE"),
    "credential-access": ("Credential Access", "CA"),
    "discovery": ("Discovery", "DISC"),
    "lateral-movement": ("Lateral Movement", "LM"),
    "collection": ("Collection", "COLL"),
    "command-and-control": ("Command and Control", "C2"),
    "exfiltration": ("Exfiltration", "EXF"),
    "impact": ("Impact", "IMP"),
}

# Fallback: Repräsentative Techniken pro Taktik (wenn kein Download möglich)
DEFAULT_TECHNIQUES = {
    "reconnaissance": [
        ("T1595", "Active Scanning"),
        ("T1592", "Gather Victim Host Information"),
        ("T1589", "Gather Victim Identity Information"),
    ],
    "resource-development": [
        ("T1583", "Acquire Infrastructure"),
        ("T1586", "Compromise Accounts"),
    ],
    "initial-access": [
        ("T1566", "Phishing"),
        ("T1190", "Exploit Public-Facing Application"),
        ("T1078", "Valid Accounts"),
        ("T1199", "Trusted Relationship"),
    ],
    "execution": [
        ("T1059", "Command and Scripting Interpreter"),
        ("T1204", "User Execution"),
        ("T1053", "Scheduled Task/Job"),
    ],
    "persistence": [
        ("T1547", "Boot or Logon Autostart Execution"),
        ("T1136", "Create Account"),
        ("T1543", "Create or Modify System Process"),
    ],
    "privilege-escalation": [
        ("T1548", "Abuse Elevation Control Mechanism"),
        ("T1134", "Access Token Manipulation"),
        ("T1068", "Exploitation for Privilege Escalation"),
    ],
    "defense-evasion": [
        ("T1070", "Indicator Removal"),
        ("T1036", "Masquerading"),
        ("T1027", "Obfuscated Files or Information"),
    ],
    "credential-access": [
        ("T1110", "Brute Force"),
        ("T1003", "OS Credential Dumping"),
        ("T1555", "Credentials from Password Stores"),
    ],
    "discovery": [
        ("T1087", "Account Discovery"),
        ("T1046", "Network Service Discovery"),
        ("T1082", "System Information Discovery"),
    ],
    "lateral-movement": [
        ("T1021", "Remote Services"),
        ("T1570", "Lateral Tool Transfer"),
        ("T1080", "Taint Shared Content"),
    ],
    "collection": [
        ("T1560", "Archive Collected Data"),
        ("T1005", "Data from Local System"),
        ("T1114", "Email Collection"),
    ],
    "command-and-control": [
        ("T1071", "Application Layer Protocol"),
        ("T1105", "Ingress Tool Transfer"),
        ("T1572", "Protocol Tunneling"),
    ],
    "exfiltration": [
        ("T1048", "Exfiltration Over Alternative Protocol"),
        ("T1041", "Exfiltration Over C2 Channel"),
        ("T1567", "Exfiltration Over Web Service"),
    ],
    "impact": [
        ("T1486", "Data Encrypted for Impact"),
        ("T1489", "Service Stop"),
        ("T1529", "System Shutdown/Reboot"),
    ],
}


async def wait_for_neo4j(driver, max_attempts: int = 30, delay: float = 2.0):
    """Wartet bis Neo4j bereit ist."""
    for attempt in range(1, max_attempts + 1):
        try:
            await driver.verify_connectivity()
            return True
        except Exception:
            if attempt < max_attempts:
                print(f"  Neo4j noch nicht bereit, versuche in {delay}s erneut ({attempt}/{max_attempts})...")
                await asyncio.sleep(delay)
            else:
                raise
    return False


def _build_stix_id_to_mitre_id(mitre_data: dict) -> dict:
    """Baut Mapping von STIX-internen IDs auf MITRE External IDs (G0016, T1566, T1566.001)."""
    stix_id_to_mitre_id = {}
    objects = mitre_data.get("objects", [])

    for obj in objects:
        obj_type = obj.get("type")
        stix_id = obj.get("id")
        if not stix_id:
            continue

        refs = obj.get("external_references") or []
        mitre_ref = next(
            (r for r in refs if r.get("source_name") == "mitre-attack"),
            None,
        )
        if not mitre_ref:
            continue

        ext_id = mitre_ref.get("external_id")
        if not ext_id:
            continue

        if obj_type == "intrusion-set":
            if ext_id.startswith("G"):
                stix_id_to_mitre_id[stix_id] = ext_id
        elif obj_type == "attack-pattern":
            if ext_id.startswith("T"):
                stix_id_to_mitre_id[stix_id] = ext_id

    return stix_id_to_mitre_id


async def create_constraints(driver):
    """Erstellt Unique-Constraints für Taktiken, Techniken und Groups."""
    async with driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT tactic_id IF NOT EXISTS FOR (t:Tactic) REQUIRE t.id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT technique_id IF NOT EXISTS FOR (t:Technique) REQUIRE t.id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT group_id IF NOT EXISTS FOR (g:Group) REQUIRE g.id IS UNIQUE"
        )


async def seed_tactics(driver):
    """Erstellt Tactic-Nodes mit id, name, short_name."""
    async with driver.session() as session:
        for phase_slug in KILL_CHAIN_PHASES:
            display_name, short_name = TACTIC_META.get(
                phase_slug, (phase_slug, phase_slug[:3].upper())
            )
            await session.run(
                """
                MERGE (t:Tactic {id: $id})
                SET t.name = $name, t.short_name = $short_name
                """,
                id=phase_slug,
                name=display_name,
                short_name=short_name,
            )
    print(f"  {len(KILL_CHAIN_PHASES)} Taktiken erstellt.")


async def create_tactic_precedes(driver):
    """Erstellt PRECEDES-Kanten zwischen Taktiken (Kill-Chain-Reihenfolge)."""
    async with driver.session() as session:
        for i in range(len(KILL_CHAIN_PHASES) - 1):
            from_id = KILL_CHAIN_PHASES[i]
            to_id = KILL_CHAIN_PHASES[i + 1]
            await session.run(
                """
                MATCH (a:Tactic {id: $from_id}), (b:Tactic {id: $to_id})
                MERGE (a)-[:PRECEDES]->(b)
                """,
                from_id=from_id,
                to_id=to_id,
            )
    print(f"  {len(KILL_CHAIN_PHASES) - 1} Taktik-PRECEDES-Kanten erstellt.")


async def seed_groups(driver, mitre_data: dict, stix_id_to_mitre_id: dict) -> int:
    """Erstellt Group-Nodes (Threat Actors) aus intrusion-set Objekten."""
    objects = mitre_data.get("objects", [])
    count = 0

    async with driver.session() as session:
        for obj in objects:
            if obj.get("type") != "intrusion-set":
                continue
            if obj.get("revoked"):
                continue
            if obj.get("x_mitre_deprecated"):
                continue

            stix_id = obj.get("id")
            ext_id = stix_id_to_mitre_id.get(stix_id)
            if not ext_id or not ext_id.startswith("G"):
                continue

            name = obj.get("name", ext_id)
            description = (obj.get("description") or "")[:500]
            aliases_raw = obj.get("aliases")
            aliases = ", ".join(aliases_raw) if isinstance(aliases_raw, list) else (aliases_raw or "")

            await session.run(
                """
                MERGE (g:Group {id: $id})
                SET g.name = $name, g.description = $description, g.aliases = $aliases
                """,
                id=ext_id,
                name=name,
                description=description,
                aliases=aliases,
            )
            count += 1
            if count % 50 == 0:
                print(f"  ...{count} Groups verarbeitet")

    print(f"  {count} Groups aus MITRE ATT&CK geladen.")
    return count


async def seed_subtechniques(driver, mitre_data: dict, stix_id_to_mitre_id: dict) -> tuple[int, int]:
    """Erstellt/aktualisiert Sub-Technique-Nodes, SUBTECHNIQUE_OF und HAS_TECHNIQUE.
    Returns: (subtechnique_count, subtechnique_of_count)
    """
    objects = mitre_data.get("objects", [])
    sub_count = 0
    rel_count = 0

    async with driver.session() as session:
        # 1. Sub-Technique-Nodes mit is_subtechnique=true
        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            if not obj.get("x_mitre_is_subtechnique"):
                continue
            if obj.get("x_mitre_deprecated"):
                continue
            if obj.get("revoked"):
                continue

            refs = obj.get("external_references") or []
            mitre_ref = next(
                (r for r in refs if r.get("source_name") == "mitre-attack"),
                None,
            )
            if not mitre_ref:
                continue
            ext_id = mitre_ref.get("external_id")
            if not ext_id or not ext_id.startswith("T"):
                continue

            name = obj.get("name", ext_id)
            description = (obj.get("description") or "")[:500]

            await session.run(
                """
                MERGE (t:Technique {id: $id})
                SET t.name = $name, t.description = $description, t.is_subtechnique = true
                """,
                id=ext_id,
                name=name,
                description=description,
            )
            sub_count += 1

        # 2. SUBTECHNIQUE_OF-Relationen
        for obj in objects:
            if obj.get("type") != "relationship":
                continue
            if obj.get("relationship_type") != "subtechnique-of":
                continue

            source_ref = obj.get("source_ref", "")
            target_ref = obj.get("target_ref", "")
            if not source_ref.startswith("attack-pattern--") or not target_ref.startswith("attack-pattern--"):
                continue

            sub_id = stix_id_to_mitre_id.get(source_ref)
            parent_id = stix_id_to_mitre_id.get(target_ref)
            if not sub_id or not parent_id:
                continue

            await session.run(
                """
                MATCH (sub:Technique {id: $sub_id}), (parent:Technique {id: $parent_id})
                MERGE (sub)-[:SUBTECHNIQUE_OF]->(parent)
                """,
                sub_id=sub_id,
                parent_id=parent_id,
            )
            rel_count += 1

        # 3. HAS_TECHNIQUE für Sub-Techniques (über Parent)
        await session.run(
            """
            MATCH (sub:Technique {is_subtechnique: true})-[:SUBTECHNIQUE_OF]->(parent:Technique)
            MATCH (tac:Tactic)-[:HAS_TECHNIQUE]->(parent)
            MERGE (tac)-[:HAS_TECHNIQUE]->(sub)
            """
        )

    print(f"  {sub_count} Sub-Techniques, {rel_count} SUBTECHNIQUE_OF-Relationen.")
    return sub_count, rel_count


async def seed_uses_technique(driver, mitre_data: dict, stix_id_to_mitre_id: dict) -> int:
    """Erstellt USES_TECHNIQUE-Relationen (Group -> Technique)."""
    objects = mitre_data.get("objects", [])
    count = 0

    async with driver.session() as session:
        for obj in objects:
            if obj.get("type") != "relationship":
                continue
            if obj.get("relationship_type") != "uses":
                continue

            source_ref = obj.get("source_ref", "")
            target_ref = obj.get("target_ref", "")
            if not source_ref.startswith("intrusion-set--"):
                continue
            if not target_ref.startswith("attack-pattern--"):
                continue

            group_id = stix_id_to_mitre_id.get(source_ref)
            technique_id = stix_id_to_mitre_id.get(target_ref)
            if not group_id or not technique_id:
                continue

            await session.run(
                """
                MATCH (g:Group {id: $group_id}), (t:Technique {id: $technique_id})
                MERGE (g)-[:USES_TECHNIQUE]->(t)
                """,
                group_id=group_id,
                technique_id=technique_id,
            )
            count += 1
            if count % 500 == 0:
                print(f"  ...{count} USES_TECHNIQUE verarbeitet")

    print(f"  {count} USES_TECHNIQUE-Relationen erstellt.")
    return count


def _try_download_mitre():
    """Versucht MITRE ATT&CK STIX-Daten herunterzuladen."""
    try:
        import requests

        print("  Lade MITRE ATT&CK Enterprise Daten herunter...")
        resp = requests.get(MITRE_URL, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print(f"  Download erfolgreich ({len(data.get('objects', []))} Objekte).")
        return data
    except Exception as e:
        print(f"  Download fehlgeschlagen: {e}")
        print("  Verwende Fallback-Techniken.")
        return None


async def seed_techniques_from_mitre(driver, mitre_data: dict):
    """Erstellt Technique-Nodes und HAS_TECHNIQUE-Kanten aus MITRE STIX-Daten."""
    objects = mitre_data.get("objects", [])
    count = 0

    async with driver.session() as session:
        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            if obj.get("x_mitre_deprecated"):
                continue
            if obj.get("revoked"):
                continue

            refs = obj.get("external_references") or []
            mitre_ref = next(
                (r for r in refs if r.get("source_name") == "mitre-attack"),
                None,
            )
            if not mitre_ref:
                continue
            ext_id = mitre_ref.get("external_id")
            if not ext_id or not ext_id.startswith("T"):
                continue

            name = obj.get("name", ext_id)
            description = (obj.get("description") or "")[:500]

            await session.run(
                "MERGE (t:Technique {id: $id}) SET t.name = $name, t.description = $description",
                id=ext_id,
                name=name,
                description=description,
            )

            for kcp in obj.get("kill_chain_phases") or []:
                if kcp.get("kill_chain_name") == "mitre-attack":
                    phase = kcp.get("phase_name")
                    if phase:
                        await session.run(
                            """
                            MATCH (tac:Tactic {id: $phase_id}), (tech:Technique {id: $tech_id})
                            MERGE (tac)-[:HAS_TECHNIQUE]->(tech)
                            """,
                            phase_id=phase,
                            tech_id=ext_id,
                        )

            count += 1
            if count % 100 == 0:
                print(f"  ...{count} Techniken verarbeitet")

    print(f"  {count} Techniken aus MITRE ATT&CK geladen.")
    return count


async def seed_techniques_fallback(driver):
    """Erstellt Fallback-Techniken wenn kein Download möglich."""
    count = 0
    async with driver.session() as session:
        for phase_slug, techniques in DEFAULT_TECHNIQUES.items():
            for tech_id, tech_name in techniques:
                await session.run(
                    "MERGE (t:Technique {id: $id}) SET t.name = $name, t.description = ''",
                    id=tech_id,
                    name=tech_name,
                )
                await session.run(
                    """
                    MATCH (tac:Tactic {id: $phase_id}), (tech:Technique {id: $tech_id})
                    MERGE (tac)-[:HAS_TECHNIQUE]->(tech)
                    """,
                    phase_id=phase_slug,
                    tech_id=tech_id,
                )
                count += 1
    print(f"  {count} Fallback-Techniken erstellt.")
    return count


async def _count_relations(driver) -> dict:
    """Zählt alle relevanten Nodes und Relationen im KG."""
    counts = {}
    async with driver.session() as session:
        for label, var in [
            ("Tactic", "tactics"),
            ("Technique", "techniques"),
            ("Group", "groups"),
        ]:
            result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            rec = await result.single()
            counts[var] = rec["c"] if rec else 0

        # Sub-Techniques (Technique mit is_subtechnique=true)
        result = await session.run(
            "MATCH (t:Technique {is_subtechnique: true}) RETURN count(t) AS c"
        )
        rec = await result.single()
        counts["subtechniques"] = rec["c"] if rec else 0

        for rel_type in ["HAS_TECHNIQUE", "USES_TECHNIQUE", "SUBTECHNIQUE_OF", "PRECEDES"]:
            result = await session.run(
                f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c"
            )
            rec = await result.single()
            key = rel_type.lower()
            counts[key] = rec["c"] if rec else 0

    return counts


async def run_validation_queries(driver):
    """Führt Validierungsqueries aus und loggt die Ergebnisse."""
    print("\n--- Validierungstests ---")
    async with driver.session() as session:
        # Test 1: APT29 sollte existieren
        result = await session.run(
            "MATCH (g:Group {name: 'APT29'}) RETURN g.id AS id, g.name AS name"
        )
        rec = await result.single()
        if rec:
            print(f"  Test 1 (APT29 existiert): id={rec['id']}, name={rec['name']}")
        else:
            print("  Test 1 (APT29 existiert): Kein Ergebnis")

        # Test 2: APT29 sollte Techniken nutzen
        result = await session.run(
            """
            MATCH (g:Group {name: 'APT29'})-[:USES_TECHNIQUE]->(t:Technique)
            RETURN t.id AS id, t.name AS name ORDER BY t.id LIMIT 10
            """
        )
        records = await result.data()
        print(f"  Test 2 (APT29 Techniken, erste 10): {len(records)} Treffer")
        for r in records[:5]:
            print(f"    - {r['id']}: {r['name']}")
        if len(records) > 5:
            print(f"    ... und {len(records) - 5} weitere")

        # Test 3: Sub-Techniques von T1566
        result = await session.run(
            """
            MATCH (sub:Technique)-[:SUBTECHNIQUE_OF]->(parent:Technique {id: 'T1566'})
            RETURN sub.id AS id, sub.name AS name
            """
        )
        records = await result.data()
        print(f"  Test 3 (Sub-Techniques von T1566): {len(records)} Treffer")
        for r in records[:5]:
            print(f"    - {r['id']}: {r['name']}")
        if len(records) > 5:
            print(f"    ... und {len(records) - 5} weitere")


async def create_technique_precedes(driver):
    """Erstellt PRECEDES-Kanten zwischen Techniken basierend auf Kill-Chain-Reihenfolge.

    Heuristik: Gehört Technik T1 zur Phase P1 und Technik T2 zur Phase P2,
    und steht P1 direkt vor P2 in der Kill Chain, dann (T1)-[:PRECEDES]->(T2).
    Techniken derselben Taktik koennen ebenfalls aufeinander folgen.
    """
    async with driver.session() as session:
        # Inter-Taktik: Phase P1 -> Phase P2
        for i in range(len(KILL_CHAIN_PHASES) - 1):
            p1 = KILL_CHAIN_PHASES[i]
            p2 = KILL_CHAIN_PHASES[i + 1]
            result = await session.run(
                """
                MATCH (tac1:Tactic {id: $p1})-[:HAS_TECHNIQUE]->(t1:Technique)
                MATCH (tac2:Tactic {id: $p2})-[:HAS_TECHNIQUE]->(t2:Technique)
                MERGE (t1)-[:PRECEDES]->(t2)
                RETURN count(*) AS edges
                """,
                p1=p1,
                p2=p2,
            )
            record = await result.single()
            edges = record["edges"] if record else 0
            print(f"  PRECEDES: {p1} -> {p2} ({edges} Kanten)")

        # Intra-Taktik: Techniken derselben Taktik
        for phase_slug in KILL_CHAIN_PHASES:
            await session.run(
                """
                MATCH (tac:Tactic {id: $phase})-[:HAS_TECHNIQUE]->(t1:Technique)
                MATCH (tac)-[:HAS_TECHNIQUE]->(t2:Technique)
                WHERE t1 <> t2
                MERGE (t1)-[:PRECEDES]->(t2)
                """,
                phase=phase_slug,
            )


async def main():
    """Hauptfunktion: Verbindet mit Neo4j und lädt MITRE-Daten."""
    print("=== MITRE ATT&CK Seed ===")
    print(f"Neo4j: {NEO4J_URI}")

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        await wait_for_neo4j(driver)
        print("Verbindung erfolgreich.")

        print("\n1. Constraints erstellen...")
        await create_constraints(driver)

        print("\n2. Taktiken laden...")
        await seed_tactics(driver)

        print("\n3. Taktik-PRECEDES erstellen...")
        await create_tactic_precedes(driver)

        print("\n4. Techniken laden...")
        mitre_data = _try_download_mitre()
        if mitre_data:
            await seed_techniques_from_mitre(driver, mitre_data)

            print("\n5. Groups, Sub-Techniques, USES_TECHNIQUE laden...")
            stix_id_to_mitre_id = _build_stix_id_to_mitre_id(mitre_data)
            await seed_groups(driver, mitre_data, stix_id_to_mitre_id)
            await seed_subtechniques(driver, mitre_data, stix_id_to_mitre_id)
            await seed_uses_technique(driver, mitre_data, stix_id_to_mitre_id)
        else:
            await seed_techniques_fallback(driver)

        print("\n6. Technik-PRECEDES erstellen...")
        await create_technique_precedes(driver)

        # Zähler und Zusammenfassung
        counts = await _count_relations(driver)
        print("\nKG Seeding abgeschlossen:")
        print(f"  - Tactics: {counts.get('tactics', 0)}")
        print(f"  - Techniques: {counts.get('techniques', 0)}")
        print(f"  - Sub-Techniques: {counts.get('subtechniques', 0)}")
        print(f"  - Groups: {counts.get('groups', 0)}")
        print(f"  - HAS_TECHNIQUE Relationen: {counts.get('has_technique', 0)}")
        print(f"  - USES_TECHNIQUE Relationen: {counts.get('uses_technique', 0)}")
        print(f"  - SUBTECHNIQUE_OF Relationen: {counts.get('subtechnique_of', 0)}")
        print(f"  - PRECEDES Relationen: {counts.get('precedes', 0)}")

        if mitre_data:
            await run_validation_queries(driver)

        print("\n=== Seed abgeschlossen ===")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
