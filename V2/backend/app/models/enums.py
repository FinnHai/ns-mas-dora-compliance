"""TIBER-EU konforme MSEL Enums."""
from __future__ import annotations

from enum import Enum
from typing import Union


class Phase(str, Enum):
    """TIBER-EU Phasen des Red-Team-Ablaufs.

    IN: Entering – Eindringen in die ICT-Systeme des Finanzinstituts.
    THROUGH: Moving – Bewegung durch die Systeme und Ausführung von Aktionen.
    OUT: Executing/Extracting – Ausführung der Ziele und Exfiltration von Daten.
    """

    IN = "IN"
    THROUGH = "THROUGH"
    OUT = "OUT"


class SecurityGoal(str, Enum):
    """Sicherheitsziele der CIA-Triade.

    CONFIDENTIALITY: Vertraulichkeit – Unbefugte dürfen keine Informationen einsehen.
    INTEGRITY: Integrität – Daten sollen unverändert und vertrauenswürdig bleiben.
    AVAILABILITY: Verfügbarkeit – Systeme und Daten sollen für Berechtigte zugänglich sein.
    """

    CONFIDENTIALITY = "CONFIDENTIALITY"
    INTEGRITY = "INTEGRITY"
    AVAILABILITY = "AVAILABILITY"


class StepStatus(str, Enum):
    """Status eines MSEL-Schritts.

    PLANNED: Geplant, noch nicht ausgeführt.
    SUCCESS: Erfolgreich ausgeführt.
    FAILED: Ausführung fehlgeschlagen.
    BLOCKED: Durch Sicherheitsmaßnahmen blockiert.
    SKIPPED: Übersprungen (z.B. nicht relevant für den Testverlauf).
    """

    PLANNED = "PLANNED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class LegUpType(str, Enum):
    """Art der Unterstützung (Leg-Up) für das Red Team.

    ACCESS: Zugang – physischer oder digitaler Zugang zu Systemen.
    INFORMATION: Information – Bereitstellung von Wissen oder Insider-Informationen.
    HARDWARE: Hardware – Bereitstellung von Geräten oder Infrastruktur.
    """

    ACCESS = "ACCESS"
    INFORMATION = "INFORMATION"
    HARDWARE = "HARDWARE"


class LegUpStatus(str, Enum):
    """Status einer Leg-Up-Anfrage.

    REQUESTED: Anfrage gestellt, Entscheidung ausstehend.
    APPROVED: Genehmigt, kann ausgeführt werden.
    DENIED: Abgelehnt.
    EXECUTED: Bereits ausgeführt/umgesetzt.
    """

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXECUTED = "EXECUTED"


class DetectionStatus(str, Enum):
    """Ob eine Angriffsaktion von der Verteidigung erkannt oder blockiert wurde.

    DETECTED: Erkannt – die Aktion wurde von Sicherheitsmechanismen erkannt.
    NOT_DETECTED: Nicht erkannt – die Aktion blieb unentdeckt.
    BLOCKED: Blockiert – die Aktion wurde verhindert oder unterbunden.
    """

    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    BLOCKED = "BLOCKED"


class ActorCategory(str, Enum):
    """Kategorie des Bedrohungsakteurs.

    NATION_STATE: Staatlicher Akteur – staatlich gestützte Angreifer.
    ORG_CRIME: Organisierte Kriminalität – kriminelle Organisationen.
    HACKTIVIST: Hacktivist – ideologisch motivierte Angreifer.
    INSIDER: Insider – Angreifer von innerhalb der Organisation.
    """

    NATION_STATE = "NATION_STATE"
    ORG_CRIME = "ORG_CRIME"
    HACKTIVIST = "HACKTIVIST"
    INSIDER = "INSIDER"


class CapabilityLevel(str, Enum):
    """Fähigkeitsstufe des Angreifers.

    LOW: Gering – eingeschränkte Ressourcen und Fähigkeiten.
    INTERMEDIATE: Mittel – moderate technische und organisatorische Kapazitäten.
    ADVANCED: Hoch – fortgeschrittene Fähigkeiten, ressourcenstark.
    """

    LOW = "LOW"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


# Union-Typ für beliebige MSEL-Enum-Werte (z.B. in Pydantic-Schemas)
MSELEnum = Union[
    Phase,
    SecurityGoal,
    StepStatus,
    LegUpType,
    LegUpStatus,
    DetectionStatus,
    ActorCategory,
    CapabilityLevel,
]
