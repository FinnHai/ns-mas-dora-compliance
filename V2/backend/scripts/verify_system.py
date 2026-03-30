#!/usr/bin/env python3
"""
Verifikationsskript für die Bachelorarbeit: Beweis der Funktionsfähigkeit
des Neuro-Symbolischen Validators.

Führt vier Tests durch:
1. Connectivity: Neo4j-Verbindung prüfen
2. Kill Chain Logic: validate_path(Reconnaissance → Initial Access) muss True sein
3. Anti-Hallucination: validate_path(Impact → Reconnaissance) muss False sein
4. DORA Constraints: Validator lehnt destruktive Aktionen ("wipe database") ab

Ausführung (Backend-Venv + Neo4j müssen laufen):
    ./run_verify.sh
    # Oder manuell:
    cd backend && .venv/bin/python -m scripts.verify_system
"""
from pathlib import Path
import sys

# Backend-Pfad für Imports hinzufügen
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

# MITRE ATT&CK Technik-IDs (bekannte Beispiele aus Enterprise)
TECH_RECON = "T1592"           # Reconnaissance (Active Scanning)
TECH_INITIAL_ACCESS = "T1566"  # Initial Access (Phishing: Spearphishing Attachment)
TECH_IMPACT = "T1485"          # Impact (Data Encrypted for Impact)

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"


def run_test(name: str, condition: bool, details: str = "") -> bool:
    """Führt einen Test aus und gibt Ergebnis mit Emoji aus."""
    status = PASS if condition else FAIL
    msg = f"{status} {name}"
    if details:
        msg += f" — {details}"
    print(msg)
    return condition


def main() -> None:
    print("\n" + "=" * 60)
    print("  Neuro-Symbolischer Validator – Systemverifikation")
    print("  (Beweis für Bachelorarbeit)")
    print("=" * 60 + "\n")

    all_passed = True

    # --- Setup ---
    print("Setup: Initialisiere Neo4jService...")
    try:
        from app.services.neo4j_connector import Neo4jService

        neo4j = Neo4jService()
        print("  Neo4jService initialisiert.\n")
    except Exception as e:
        print(f"{FAIL} Setup fehlgeschlagen: {e}")
        if "No module named 'neo4j'" in str(e):
            print("\n→ Nutze das Backend-Venv: ./run_verify.sh")
            print("  Oder: cd backend && .venv/bin/python -m scripts.verify_system")
        sys.exit(1)

    # --- Test 1: Connectivity ---
    print("Test 1 (Connectivity): Prüfe Neo4j-Verbindung...")
    ok = neo4j.verify_connectivity()
    all_passed &= run_test(
        "Connectivity",
        ok,
        "DB erreichbar" if ok else "DB nicht erreichbar – Neo4j läuft?",
    )
    if not ok:
        print("\nAbbruch: Ohne DB-Verbindung können weitere Tests nicht laufen.")
        print("Stelle sicher, dass Neo4j läuft und backend/scripts/seed_mitre.py ausgeführt wurde (z.B. via ./start.sh).")
        sys.exit(1)

    # --- Test 2: Kill Chain Logic ---
    print("\nTest 2 (Kill Chain Logic): Reconnaissance → Initial Access muss verbunden sein...")
    result = neo4j.validate_path(TECH_RECON, TECH_INITIAL_ACCESS)
    all_passed &= run_test(
        "Kill Chain Logic",
        result is True,
        f"validate_path({TECH_RECON}, {TECH_INITIAL_ACCESS}) = {result}",
    )

    # --- Test 3: Anti-Hallucination ---
    print("\nTest 3 (Anti-Hallucination): Impact → Reconnaissance darf NICHT verbunden sein...")
    result = neo4j.validate_path(TECH_IMPACT, TECH_RECON)
    all_passed &= run_test(
        "Anti-Hallucination",
        result is False,
        f"validate_path({TECH_IMPACT}, {TECH_RECON}) = {result}",
    )

    # --- Test 4: DORA Constraints ---
    print("\nTest 4 (DORA Constraints): Validator lehnt 'wipe database' ab...")
    try:
        from app.graph.nodes.validator import validate_step

        # Fake-State: zwei Schritte, der zweite enthält "wipe database"
        fake_state = {
            "msel_items": [
                {"technique_id": TECH_RECON, "action_description": "Scan network"},
                {
                    "technique_id": TECH_INITIAL_ACCESS,
                    "action_description": "wipe database to destroy evidence",
                    "target": "server",
                    "success_criteria": "access",
                },
            ],
            "target_cif": None,
        }
        out = validate_step(fake_state)
        has_error = out.get("validation_error") is not None
        step_removed = len(out.get("msel_items", [])) == 1
        all_passed &= run_test(
            "DORA Constraints",
            has_error and step_removed,
            f"validation_error={out.get('validation_error', 'None')}, Schritte={len(out.get('msel_items', []))}",
        )
    except Exception as e:
        all_passed &= run_test("DORA Constraints", False, str(e))

    # --- Zusammenfassung ---
    print("\n" + "=" * 60)
    if all_passed:
        print(f"{PASS} Alle Tests bestanden – Validator funktioniert wie spezifiziert.")
    else:
        print(f"{FAIL} Mindestens ein Test fehlgeschlagen.")
    print("=" * 60 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
