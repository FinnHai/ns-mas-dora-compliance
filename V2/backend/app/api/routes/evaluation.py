"""Evaluation-Routen: Neuro vs. Baseline Vergleich."""
from fastapi import APIRouter

from app.schemas.scenarios import ScenarioGenerateRequest
from app.schemas.evaluation import EvaluationCompareResponse

router = APIRouter()


@router.post("/compare", response_model=EvaluationCompareResponse)
async def evaluate_compare(request: ScenarioGenerateRequest):
    """Generiert Szenario in beiden Modi (neuro + baseline) und vergleicht die Action Alignment Scores."""
    from app.services.scenario_service import scenario_service

    neuro = await scenario_service.generate(
        request, use_graph_validation=True, include_validation=True
    )
    baseline = await scenario_service.generate(
        request, use_graph_validation=False, include_validation=True
    )

    neuro_validation = neuro.validation
    baseline_validation = baseline.validation

    if not neuro_validation and neuro.events:
        from app.services.validation_service import validation_service
        from app.schemas.validation import ValidationRequest, ScenarioEventInput

        req = ValidationRequest(
            events=[
                ScenarioEventInput(
                    order=e.order,
                    description=e.description,
                    tactic_id=e.tactic_id,
                    technique_id=e.technique_id,
                )
                for e in neuro.events
            ]
        )
        neuro_validation = await validation_service.validate(req)

    if not baseline_validation and baseline.events:
        from app.services.validation_service import validation_service
        from app.schemas.validation import ValidationRequest, ScenarioEventInput

        req = ValidationRequest(
            events=[
                ScenarioEventInput(
                    order=e.order,
                    description=e.description,
                    tactic_id=e.tactic_id,
                    technique_id=e.technique_id,
                )
                for e in baseline.events
            ]
        )
        baseline_validation = await validation_service.validate(req)

    return EvaluationCompareResponse(
        neuro=neuro,
        baseline=baseline,
        neuro_validation=neuro_validation or _empty_validation(),
        baseline_validation=baseline_validation or _empty_validation(),
    )


def _empty_validation():
    """Leere ValidationResponse wenn keine Events."""
    from app.schemas.validation import ValidationResponse

    return ValidationResponse(
        overall_valid=False,
        action_alignment_score=0.0,
        results=[],
        sequence_valid=False,
        sequence_message="Keine Events",
    )
