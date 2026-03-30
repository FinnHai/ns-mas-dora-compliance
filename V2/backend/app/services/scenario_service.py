"""Szenario-Service: Koordination zwischen Agenten und API.

Verwendet das konsolidierte TIBER-EU Graph-System (graph/main.py)
mit Generator-Validator-Schleife und Neo4j-basierter Pfad-Validierung.
"""
import uuid

from app.graph.main import run_scenario, run_scenario_stream
from app.graph.state import ScenarioState
from app.models.enums import ActorCategory, CapabilityLevel
from app.models.strategy import CriticalFunction, ScenarioMetadata, ThreatActorProfile
from app.schemas.scenarios import (
    ScenarioEvent,
    ScenarioGenerateRequest,
    ScenarioResponse,
    ScenarioStatus,
    ExecutionStep,
)
from app.schemas.agent_config import AgentConfig
from app.schemas.validation import ValidationRequest, ScenarioEventInput


def _build_threat_actor(threat_context: str) -> ThreatActorProfile:
    """Leitet ein ThreatActorProfile aus dem Bedrohungskontext ab."""
    context_lower = threat_context.lower()

    # Heuristik: Kategorie aus Kontext ableiten
    if any(w in context_lower for w in ["apt", "nation", "staat", "government"]):
        category = ActorCategory.NATION_STATE
        capability = CapabilityLevel.ADVANCED
    elif any(w in context_lower for w in ["ransomware", "crime", "kriminell", "financial"]):
        category = ActorCategory.ORG_CRIME
        capability = CapabilityLevel.INTERMEDIATE
    elif any(w in context_lower for w in ["insider", "mitarbeiter", "employee"]):
        category = ActorCategory.INSIDER
        capability = CapabilityLevel.INTERMEDIATE
    elif any(w in context_lower for w in ["hacktivist", "activist", "protest"]):
        category = ActorCategory.HACKTIVIST
        capability = CapabilityLevel.LOW
    else:
        category = ActorCategory.ORG_CRIME
        capability = CapabilityLevel.INTERMEDIATE

    return ThreatActorProfile(
        name="Derived Threat Actor",
        category=category,
        motivation=["financial", "espionage"],
        targeted_cifs=["primary-system"],
        capability=capability,
        known_techniques=[],  # Leer = alle Techniken erlaubt
        description=threat_context,
    )


def _build_default_cif() -> CriticalFunction:
    """Erstellt eine Standard-CriticalFunction für den Prototyp."""
    return CriticalFunction(
        id="cif-default",
        name="Primary Business System",
        sub_functions=["Payment Processing", "Customer Data Management"],
        supporting_assets=["ERP Server", "Database Server", "Email Server"],
        flags=["Screenshot of DB access", "Exfiltrated test data"],
    )


def _msel_items_to_events(msel_items: list) -> list[ScenarioEvent]:
    """Konvertiert MSELItems in das einfachere ScenarioEvent-Format."""
    events = []
    for i, item in enumerate(msel_items):
        if isinstance(item, dict):
            desc = item.get("action_description", "")
            tactic = item.get("tactic", "")
            technique = item.get("technique_id", "")
            phase = item.get("phase", "")
            step_index = item.get("step_index", i + 1)
        else:
            desc = getattr(item, "action_description", "")
            tactic = getattr(item, "tactic", "")
            technique = getattr(item, "technique_id", "")
            phase_val = getattr(item, "phase", None)
            phase = phase_val.value if hasattr(phase_val, "value") else str(phase_val) if phase_val else ""
            step_index = getattr(item, "step_index", i + 1)

        events.append(ScenarioEvent(
            order=step_index,
            description=f"[{phase}] {desc}" if phase else desc,
            tactic_id=tactic if tactic else None,
            technique_id=technique if technique else None,
            timestamp_offset_hours=float(step_index),
        ))
    return events


def _build_execution_trace(msel_items: list, validation_error: str | None) -> list[ExecutionStep]:
    """Baut einen Execution Trace aus den MSEL-Items."""
    from datetime import datetime

    steps = []
    for i, item in enumerate(msel_items):
        if isinstance(item, dict):
            desc = item.get("action_description", "")
            tech = item.get("technique_id", "")
            phase = item.get("phase", "")
        else:
            desc = getattr(item, "action_description", "")
            tech = getattr(item, "technique_id", "")
            phase_val = getattr(item, "phase", None)
            phase = phase_val.value if hasattr(phase_val, "value") else str(phase_val) if phase_val else ""

        steps.append(ExecutionStep(
            step="generator",
            iteration=i + 1,
            timestamp=datetime.utcnow().isoformat() + "Z",
            detail=f"[{phase}] {tech}: {desc[:80]}",
            payload={"technique_id": tech, "phase": phase},
        ))
        steps.append(ExecutionStep(
            step="validator",
            iteration=i + 1,
            timestamp=datetime.utcnow().isoformat() + "Z",
            detail="Validiert" if not validation_error else f"Fehler: {validation_error}",
            payload={"approved": not validation_error},
        ))
    return steps


class ScenarioService:
    """Service für Szenario-Generierung.

    Nutzt das konsolidierte TIBER-EU Graph-System mit:
    - Generator: LLM-basierte MSEL-Schritt-Generierung
    - Validator: Neo4j-basierte Pfad-Validierung + DORA-Constraints
    """

    async def generate(
        self,
        request: ScenarioGenerateRequest,
        use_graph_validation: bool = True,
        include_validation: bool = True,
    ) -> ScenarioResponse:
        """Startet die Szenario-Generierung.

        Args:
            request: Generierungsanfrage mit Bedrohungskontext
            use_graph_validation: Wenn False, wird die Baseline ohne Graph-Validierung genutzt
        """
        scenario_id = str(uuid.uuid4())
        config = request.agent_config or AgentConfig()

        try:
            threat_actor = _build_threat_actor(request.threat_context)
            target_cif = _build_default_cif()

            initial_state: ScenarioState = {
                "msel_items": [],
                "validation_error": None,
                "target_cif": target_cif,
                "threat_actor": threat_actor,
                "scenario_metadata": ScenarioMetadata(
                    id=scenario_id,
                    name=f"Scenario {scenario_id[:8]}",
                    threat_actor=threat_actor,
                    target_cif=target_cif,
                    is_scenario_x=False,
                    constraints=[],
                ),
                "scenario_id": scenario_id,
                "flag_achieved": False,
                "max_steps": config.max_events,
                "agent_config": config,
            }

            if use_graph_validation:
                final_state = await run_scenario(initial_state)
            else:
                final_state = await self._run_baseline(initial_state)

            msel_items = final_state.get("msel_items", [])
            events = _msel_items_to_events(msel_items)
            trace = _build_execution_trace(
                msel_items, final_state.get("validation_error")
            )

            audit_feedback = []
            if final_state.get("validation_error"):
                audit_feedback.append(final_state["validation_error"])
            if final_state.get("flag_achieved"):
                audit_feedback.append("Flag achieved - Szenario erfolgreich abgeschlossen.")

            validation = None
            if include_validation and events:
                validation = await self._validate_events(events)

            return ScenarioResponse(
                id=scenario_id,
                status=ScenarioStatus.COMPLETED,
                events=events,
                threat_context=request.threat_context,
                audit_feedback=audit_feedback,
                execution_trace=trace,
                validation=validation,
            )
        except Exception as e:
            return ScenarioResponse(
                id=scenario_id,
                status=ScenarioStatus.FAILED,
                events=[],
                threat_context=request.threat_context,
                audit_feedback=[],
                error_message=str(e),
            )

    async def _validate_events(self, events: list[ScenarioEvent]):
        """Fuehrt quantitative Evaluation der Events durch."""
        from app.services.validation_service import validation_service

        req = ValidationRequest(
            events=[
                ScenarioEventInput(
                    order=e.order,
                    description=e.description,
                    tactic_id=e.tactic_id,
                    technique_id=e.technique_id,
                )
                for e in events
            ]
        )
        return await validation_service.validate(req)

    async def _run_baseline(self, initial_state: ScenarioState) -> ScenarioState:
        """Baseline: Generiert MSEL-Schritte OHNE Graph-Validierung.

        Nutzt nur den Generator-Node ohne Validator, um den Mehrwert
        des neuro-symbolischen Ansatzes messbar zu machen (FF3).
        """
        from app.graph.nodes.generator import generate_step

        state = dict(initial_state)
        max_steps = state.get("max_steps", 10)

        for _ in range(max_steps):
            state = await generate_step(state)
            msel_items = state.get("msel_items", [])
            if len(msel_items) >= max_steps:
                break

        return state

    async def generate_stream(
        self,
        request: ScenarioGenerateRequest,
        use_graph_validation: bool = True,
        include_validation: bool = True,
    ):
        """Streamt die Szenario-Generierung mit Live-Logs.

        Yields SSE-kompatible dicts: {"type": "log"|"complete"|"error", "message": str, ...}
        """
        scenario_id = str(uuid.uuid4())
        config = request.agent_config or AgentConfig()

        try:
            threat_actor = _build_threat_actor(request.threat_context)
            target_cif = _build_default_cif()

            initial_state: ScenarioState = {
                "msel_items": [],
                "validation_error": None,
                "target_cif": target_cif,
                "threat_actor": threat_actor,
                "scenario_metadata": ScenarioMetadata(
                    id=scenario_id,
                    name=f"Scenario {scenario_id[:8]}",
                    threat_actor=threat_actor,
                    target_cif=target_cif,
                    is_scenario_x=False,
                    constraints=[],
                ),
                "scenario_id": scenario_id,
                "flag_achieved": False,
                "max_steps": config.max_events,
                "agent_config": config,
            }

            yield {"type": "log", "message": f"Szenario-Generierung gestartet (max. {config.max_events} Schritte)"}

            if use_graph_validation:
                final_state = None
                async for node_name, data in run_scenario_stream(initial_state):
                    state = data.get("state", data) if isinstance(data, dict) else {}
                    final_state = state

                    if node_name == "generator":
                        step = data.get("step", 0)
                        tech = data.get("technique_id", "")
                        action = data.get("action", "")
                        yield {"type": "log", "message": f"Schritt {step} generiert: [{tech}] {action}"}
                    elif node_name == "validator":
                        if data.get("approved"):
                            if data.get("flag_achieved"):
                                yield {"type": "log", "message": "Flag erreicht – Szenario abgeschlossen!"}
                            else:
                                yield {"type": "log", "message": "Schritt validiert – weiter zum nächsten"}
                        else:
                            err = data.get("error", "Unbekannter Fehler")
                            yield {"type": "log", "message": f"Schritt abgelehnt: {err}"}

                if final_state is None:
                    final_state = initial_state
            else:
                yield {"type": "log", "message": "Baseline-Modus: Generierung ohne Graph-Validierung"}
                final_state = await self._run_baseline(initial_state)

            msel_items = final_state.get("msel_items", [])
            events = _msel_items_to_events(msel_items)
            trace = _build_execution_trace(msel_items, final_state.get("validation_error"))

            audit_feedback = []
            if final_state.get("validation_error"):
                audit_feedback.append(final_state["validation_error"])
            if final_state.get("flag_achieved"):
                audit_feedback.append("Flag achieved - Szenario erfolgreich abgeschlossen.")

            validation = None
            if include_validation and events:
                validation = await self._validate_events(events)

            result = ScenarioResponse(
                id=scenario_id,
                status=ScenarioStatus.COMPLETED,
                events=events,
                threat_context=request.threat_context,
                audit_feedback=audit_feedback,
                execution_trace=trace,
                validation=validation,
            )
            yield {"type": "complete", "result": result.model_dump()}

        except Exception as e:
            yield {"type": "error", "message": str(e)}
            yield {
                "type": "complete",
                "result": ScenarioResponse(
                    id=scenario_id,
                    status=ScenarioStatus.FAILED,
                    events=[],
                    threat_context=request.threat_context,
                    audit_feedback=[],
                    error_message=str(e),
                ).model_dump(),
            }


scenario_service = ScenarioService()
