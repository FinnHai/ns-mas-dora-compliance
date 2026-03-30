"""KG Auditor: Validiert TTPScenario gegen Neo4j."""
import logging

print("[Startup]     kg_auditor: start...", flush=True)
from app.models.ns_mas_schemas import (
    CorrectionHint,
    StepValidation,
    TTPScenario,
    TTPStep,
    ValidationReport,
)
print("[Startup]     kg_auditor: ns_mas_schemas OK", flush=True)
from app.rag.nvd_client import NVDClient
print("[Startup]     kg_auditor: NVDClient OK", flush=True)
from app.services.neo4j_connector import Neo4jService  # Neo4j-Import lazy in connector
print("[Startup]     kg_auditor: OK", flush=True)

logger = logging.getLogger(__name__)

# Taktik → Phase
TACTIC_TO_PHASE: dict[str, str] = {
    "reconnaissance": "in",
    "resource-development": "in",
    "initial-access": "in",
    "execution": "in",
    "persistence": "through",
    "privilege-escalation": "through",
    "defense-evasion": "through",
    "credential-access": "through",
    "discovery": "through",
    "lateral-movement": "through",
    "collection": "through",
    "command-and-control": "through",
    "exfiltration": "out",
    "impact": "out",
}

# Phase → Taktiken (für akteursspezifische Correction Hints)
PHASE_TO_TACTICS: dict[str, list[str]] = {
    "in": ["reconnaissance", "resource-development", "initial-access", "execution"],
    "through": [
        "persistence",
        "privilege-escalation",
        "defense-evasion",
        "credential-access",
        "discovery",
        "lateral-movement",
        "collection",
        "command-and-control",
    ],
    "out": ["exfiltration", "impact"],
}


def _normalize_tech_id(tech_id: str) -> str:
    """Normalisiert Technik-ID (T1566.001 -> T1566 für Haupttechnik-Lookup)."""
    s = (tech_id or "").strip()
    if "." in s:
        return s.split(".")[0]
    return s


def _get_expected_phase(phase: str) -> str:
    return phase if phase in ("in", "through", "out") else "through"


def _tactic_matches_phase(technique_tactic: str, expected_phase: str) -> bool:
    """Prüft ob Taktik zur Phase passt."""
    tactic_phase = TACTIC_TO_PHASE.get(
        (technique_tactic or "").lower().strip(), "through"
    )
    return tactic_phase == expected_phase


def _suggest_similar_techniques(neo4j: Neo4jService, invalid_id: str) -> list[str]:
    """Schlägt ähnliche Technik-IDs vor (z.B. aus derselben Taktik)."""
    suggestions: list[str] = []
    try:
        # Präfix-Match: T1566 -> T1566.001, T1566.002
        base_id = _normalize_tech_id(invalid_id)
        driver = neo4j._get_driver()
        with driver.session() as session:
            result = session.run(
                """
                MATCH (t:Technique)
                WHERE t.id STARTS WITH $prefix OR t.id = $base
                RETURN t.id AS id
                LIMIT 5
                """,
                prefix=base_id + ".",
                base=base_id,
            )
            for r in result:
                sid = r.get("id")
                if sid and sid != invalid_id:
                    suggestions.append(sid)
    except Exception as e:
        logger.debug("Suggest similar techniques: %s", e)
    return suggestions[:3]


async def run_kg_auditor(
    ttp_scenario: TTPScenario,
    auditor_iterations: int = 0,
) -> ValidationReport:
    """
    Validiert TTPScenario gegen Neo4j (DR1, DR2).

    Prüfungen: ID-Existenz, Taktik-Zuordnung, Pfad-Erreichbarkeit,
    Phasenkonformität, CVE-Validität, Duplikat-Check.
    """
    neo4j = Neo4jService()
    nvd = NVDClient()
    actor_techniques = neo4j.get_techniques_for_group(ttp_scenario.threat_actor)

    steps_flat = ttp_scenario.get_all_steps_flat()
    step_validations: list[StepValidation] = []
    correction_hints: list[CorrectionHint] = []
    passed = True

    prev_tech_id: str | None = None
    prev_tech_id_full: str | None = None  # Für Duplikat-Check: vollständige ID (Subtechniken distinkt)
    max_phase_order = 0
    phase_order = {"in": 0, "through": 1, "out": 2}

    for step in steps_flat:
        tech_id = _normalize_tech_id(step.technique_id)
        tech_id_full = (step.technique_id or "").strip()
        expected_phase = "through"
        for ps in ttp_scenario.phases:
            if step in ps.steps:
                expected_phase = ps.phase
                break

        id_exists = neo4j.technique_exists(tech_id)
        kg_tactics = neo4j.get_technique_tactics(tech_id) if id_exists else []
        tactic_match = id_exists and any(
            _tactic_matches_phase(t, expected_phase) for t in (kg_tactics or [])
        )

        path_reachable = True
        if id_exists:
            path_reachable = neo4j.validate_path(prev_tech_id, tech_id)

        # Phasenkonformität: in -> through -> out, kein Rücksprung
        current_phase_order = phase_order.get(expected_phase, 1)
        phase_conform = current_phase_order >= max_phase_order
        max_phase_order = max(max_phase_order, current_phase_order)

        cve_valid = True
        if step.cve_references:
            for cve in step.cve_references:
                if not nvd.validate_cve(cve):
                    cve_valid = False
                    break

        # Duplikat-Check: benachbarte gleiche technique_id (vollständige ID, Subtechniken distinkt)
        dup_warning = prev_tech_id_full == tech_id_full and prev_tech_id_full != ""
        if dup_warning:
            passed = False
            correction_hints.append(
                CorrectionHint(
                    step_id=step.step_id,
                    technique_id=tech_id_full,
                    message="Duplikat: Benachbarte Schritte mit gleicher Technik-ID.",
                    suggested_technique_id=None,
                )
            )

        if not id_exists:
            passed = False
            suggestions = _suggest_similar_techniques(neo4j, tech_id)
            correction_hints.append(
                CorrectionHint(
                    step_id=step.step_id,
                    technique_id=tech_id,
                    message=f"Technik-ID {tech_id} existiert nicht im MITRE ATT&CK Graph.",
                    suggested_technique_id=suggestions[0] if suggestions else None,
                )
            )

        if not path_reachable and id_exists:
            passed = False
            correction_hints.append(
                CorrectionHint(
                    step_id=step.step_id,
                    technique_id=tech_id,
                    message=f"Kein kausaler Pfad von {prev_tech_id or 'Start'} zu {tech_id}.",
                    suggested_technique_id=None,
                )
            )

        if not tactic_match and id_exists:
            passed = False
            message = f"Taktik passt nicht zur Phase {expected_phase}."
            suggested_id = None
            if actor_techniques:
                phase_tactics = PHASE_TO_TACTICS.get(expected_phase, [])
                valid_alternatives = [
                    t
                    for t in actor_techniques
                    if t.get("tactic") in phase_tactics
                ]
                if valid_alternatives:
                    alternatives_str = ", ".join(
                        f"{t['id']} ({t['name']})" for t in valid_alternatives[:5]
                    )
                    message += f" Alternativen für {ttp_scenario.threat_actor} in Phase {expected_phase}: {alternatives_str}"
                    suggested_id = valid_alternatives[0]["id"]
            correction_hints.append(
                CorrectionHint(
                    step_id=step.step_id,
                    technique_id=tech_id,
                    message=message,
                    suggested_technique_id=suggested_id,
                )
            )

        if not phase_conform:
            passed = False
            correction_hints.append(
                CorrectionHint(
                    step_id=step.step_id,
                    technique_id=tech_id,
                    message=f"Phasenreihenfolge verletzt: {expected_phase} nach vorheriger Phase.",
                    suggested_technique_id=None,
                )
            )

        step_validations.append(
            StepValidation(
                step_id=step.step_id,
                technique_id=tech_id,
                id_exists=id_exists,
                tactic_match=tactic_match,
                path_reachable=path_reachable,
                phase_conform=phase_conform,
                cve_valid=cve_valid,
                eligibility_score=None,
            )
        )

        prev_tech_id = tech_id
        prev_tech_id_full = tech_id_full

    return ValidationReport(
        passed=passed,
        steps=step_validations,
        correction_hints=correction_hints,
        auditor_iterations=auditor_iterations,
    )
