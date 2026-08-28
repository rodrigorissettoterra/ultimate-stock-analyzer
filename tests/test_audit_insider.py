from datetime import date

from ultimate_stock_analyzer.quality.audit import (
    AuditEvent,
    AuditSeverity,
    AuditorRecord,
    analyze_audit_risk,
    auditor_change_events,
)
from ultimate_stock_analyzer.quality.insider import (
    InsiderRole,
    InsiderTransaction,
    analyze_insider_alignment,
)


def test_critical_audit_event_blocks() -> None:
    result = analyze_audit_risk([
        AuditEvent(
            event_type="QUALIFIED_AUDIT_OPINION",
            severity=AuditSeverity.CRITICAL,
            source="CVM_SYNTHETIC_FIXTURE",
            description="Material synthetic qualification for test only.",
        )
    ])
    assert result.blocked
    assert result.risk_score >= 70


def test_repeated_auditor_changes_create_warning() -> None:
    records = [
        AuditorRecord(date(2022, 1, 1), "A", "Auditor A", "CVM_FRE"),
        AuditorRecord(date(2024, 1, 1), "B", "Auditor B", "CVM_FRE"),
        AuditorRecord(date(2026, 1, 1), "C", "Auditor C", "CVM_FRE"),
    ]
    events = auditor_change_events(records)
    result = analyze_audit_risk(events)
    assert "FREQUENT_AUDITOR_CHANGES" in result.flags
    assert not result.blocked


def test_insider_alignment_uses_transactions_as_evidence_not_oracle() -> None:
    purchases = [
        InsiderTransaction(
            reference_date=date(2026, 6, 1 + index),
            role=InsiderRole.EXECUTIVE,
            transaction_type="COMPRA",
            quantity=1000.0,
            price=10.0,
            source="CVM_SYNTHETIC_FIXTURE",
        )
        for index in range(6)
    ]
    result = analyze_insider_alignment(purchases)
    assert result.score > 50
    assert result.confidence == 1.0
    assert not result.flags
