from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise


class AuditSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    MATERIAL = "MATERIAL"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    severity: AuditSeverity
    source: str
    description: str
    reference_date: date | None = None


@dataclass(frozen=True, slots=True)
class AuditorRecord:
    reference_date: date
    auditor_id: str
    auditor_name: str
    source: str


@dataclass(frozen=True, slots=True)
class AuditRiskAnalysis:
    risk_score: float
    flags: tuple[str, ...]
    blocked: bool
    events: tuple[AuditEvent, ...]


def auditor_change_events(records: list[AuditorRecord]) -> list[AuditEvent]:
    ordered = sorted(records, key=lambda item: item.reference_date)
    changes: list[AuditEvent] = []
    for previous, current in pairwise(ordered):
        if previous.auditor_id.strip() == current.auditor_id.strip():
            continue
        changes.append(
            AuditEvent(
                event_type="AUDITOR_CHANGE",
                severity=AuditSeverity.INFO,
                source=current.source,
                description=f"Independent auditor changed from {previous.auditor_name} to {current.auditor_name}.",
                reference_date=current.reference_date,
            )
        )
    if len(changes) >= 2:
        changes.append(
            AuditEvent(
                event_type="FREQUENT_AUDITOR_CHANGES",
                severity=AuditSeverity.WARNING,
                source="DERIVED_FROM_CVM_FRE",
                description="Two or more independent-auditor changes observed in supplied history.",
                reference_date=ordered[-1].reference_date if ordered else None,
            )
        )
    return changes


def analyze_audit_risk(events: list[AuditEvent]) -> AuditRiskAnalysis:
    penalties = {
        AuditSeverity.INFO: 2.0,
        AuditSeverity.WARNING: 10.0,
        AuditSeverity.MATERIAL: 30.0,
        AuditSeverity.CRITICAL: 70.0,
    }
    risk = min(100.0, sum(penalties[event.severity] for event in events))
    flags = tuple(sorted({event.event_type for event in events if event.severity != AuditSeverity.INFO}))
    blocked = any(event.severity == AuditSeverity.CRITICAL for event in events)
    return AuditRiskAnalysis(
        risk_score=risk,
        flags=flags,
        blocked=blocked,
        events=tuple(events),
    )
