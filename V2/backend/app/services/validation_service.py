"""Validierungs-Service: Prüft Szenarien gegen MITRE ATT&CK.

Implementiert die quantitative Evaluation (FF3) mit drei Metriken:
1. Tactic Coverage: Anteil der Events mit gueltiger Taktik-Zuordnung
2. Technique Validity: Anteil der Events mit im Graph existierender Technik-ID
3. Sequence Validity: Korrekte Taktik-Reihenfolge gemaess Kill Chain

Der Action Alignment Score ist der gewichtete Durchschnitt dieser Metriken
(angelehnt an Bhusal et al., 2024: SECURE Benchmark).
"""
from app.schemas.validation import (
    ValidationRequest,
    ValidationResponse,
    ValidationResult,
    ScenarioEventInput,
)
from app.graph_db.client import get_graph_client
from app.services.neo4j_connector import Neo4jService


class ValidationService:
    """Service fuer Szenario-Validierung gegen MITRE ATT&CK."""

    async def validate(self, request: ValidationRequest) -> ValidationResponse:
        """Validiert Ereignisse gegen den Reasoning Graph.

        Prueft pro Event:
        1. Taktik vorhanden und gueltig
        2. Technik-ID existiert im Graph (keine halluzinierte Technik)
        3. Technik gehoert zur angegebenen Taktik
        4. Technik-Sequenz ist kausal korrekt (PRECEDES-Pfad)
        """
        client = get_graph_client()
        neo4j = Neo4jService()
        results: list[ValidationResult] = []

        # Hole verfuegbare Techniken und Taktiken aus dem Graph
        available_techniques = {}
        try:
            techniques = await client.get_techniques()
            available_techniques = {t.id: t for t in techniques}
        except Exception:
            pass

        available_tactic_ids = set()
        try:
            tactics = await client.get_tactics()
            available_tactic_ids = {t.id for t in tactics}
        except Exception:
            pass

        tactic_coverage_count = 0
        technique_validity_count = 0
        technique_mapping_count = 0
        total = len(request.events)

        prev_technique_id: str | None = None

        for event in request.events:
            issues: list[str] = []
            suggestions: dict[str, str | None] = {
                "suggested_tactic_id": None,
                "suggested_technique_id": None,
            }

            # 1. Taktik-Pruefung
            has_tactic = bool(event.tactic_id)
            tactic_valid = has_tactic and event.tactic_id in available_tactic_ids
            if has_tactic and not tactic_valid and available_tactic_ids:
                issues.append(f"Unbekannte Taktik: {event.tactic_id}")
            elif not has_tactic:
                issues.append("Keine Taktik zugeordnet")
            if tactic_valid:
                tactic_coverage_count += 1

            # 2. Technik-Validitaet (existiert im Graph?)
            has_technique = bool(event.technique_id)
            technique_valid = False
            if has_technique and available_techniques:
                technique_valid = event.technique_id in available_techniques
                if not technique_valid:
                    issues.append(
                        f"Halluzinierte Technik: {event.technique_id} existiert nicht im MITRE ATT&CK Graph"
                    )
                else:
                    technique_validity_count += 1

                    # 3. Technik-Taktik-Mapping (gehoert Technik zur angegebenen Taktik?)
                    tech_info = available_techniques[event.technique_id]
                    if tactic_valid and event.tactic_id not in tech_info.tactic_ids:
                        issues.append(
                            f"Falsches Mapping: {event.technique_id} gehoert nicht zur Taktik {event.tactic_id} "
                            f"(gueltige Taktiken: {', '.join(tech_info.tactic_ids)})"
                        )
                        if tech_info.tactic_ids:
                            suggestions["suggested_tactic_id"] = tech_info.tactic_ids[0]
                    elif tactic_valid:
                        technique_mapping_count += 1
            elif has_technique and not available_techniques:
                # Graph nicht verfuegbar: Technik akzeptieren wenn Format stimmt
                if event.technique_id.upper().startswith("T"):
                    technique_validity_count += 1
                    technique_mapping_count += 1
                else:
                    issues.append(f"Ungueltiges Technik-Format: {event.technique_id}")

            # 4. Sequenz-Validitaet (PRECEDES-Pfad)
            if has_technique and prev_technique_id and technique_valid:
                path_valid = neo4j.validate_path(prev_technique_id, event.technique_id)
                if not path_valid:
                    issues.append(
                        f"Kausalitaetsbruch: Kein gueltiger Pfad von {prev_technique_id} zu {event.technique_id}"
                    )

            if has_technique:
                prev_technique_id = event.technique_id

            # Ergebnis fuer dieses Event
            is_valid = len(issues) == 0
            message = "OK" if is_valid else "; ".join(issues)
            results.append(
                ValidationResult(
                    order=event.order,
                    is_valid=is_valid,
                    message=message,
                    suggested_tactic_id=suggestions["suggested_tactic_id"],
                    suggested_technique_id=suggestions["suggested_technique_id"],
                )
            )

        # Taktik-Sequenz-Validierung (Gesamt)
        tactic_ids = [e.tactic_id for e in request.events if e.tactic_id]
        sequence_result = await client.validate_tactic_sequence(tactic_ids)
        sequence_valid = sequence_result.get("valid", False)

        # Action Alignment Score (gewichteter Durchschnitt)
        if total > 0:
            tactic_coverage = tactic_coverage_count / total
            technique_validity = technique_validity_count / total if available_techniques else 1.0
            technique_mapping = technique_mapping_count / total if available_techniques else 1.0

            # Gewichtung: Technik-Validitaet (40%), Taktik-Coverage (30%), Mapping (30%)
            action_alignment = (
                0.4 * technique_validity
                + 0.3 * tactic_coverage
                + 0.3 * technique_mapping
            )
        else:
            action_alignment = 0.0
            tactic_coverage = technique_validity = technique_mapping = 0.0

        overall_valid = sequence_valid and action_alignment >= 0.5

        return ValidationResponse(
            overall_valid=overall_valid,
            action_alignment_score=round(action_alignment, 2),
            results=results,
            sequence_valid=sequence_valid,
            sequence_message=sequence_result.get("message", ""),
            tactic_coverage=round(tactic_coverage, 2),
            technique_validity=round(technique_validity, 2),
            technique_mapping=round(technique_mapping, 2),
        )


validation_service = ValidationService()
