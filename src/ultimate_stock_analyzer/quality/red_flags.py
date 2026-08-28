from __future__ import annotations

from datetime import date

from ultimate_stock_analyzer.domain.models import RedFlag


def evaluate_red_flags(
    *,
    equity: float | None = None,
    judicial_recovery: bool = False,
    confirmed_default: bool = False,
    adverse_auditor_opinion: bool = False,
    confirmed_accounting_fraud: bool = False,
    latest_financial_publication: date | None = None,
    as_of: date | None = None,
    max_staleness_days: int = 220,
) -> list[RedFlag]:
    flags: list[RedFlag] = []
    if equity is not None and equity < 0:
        flags.append(RedFlag(code="NEGATIVE_EQUITY", reason="Negative shareholders' equity", blocking=True, severity=5))
    if judicial_recovery:
        flags.append(RedFlag(code="JUDICIAL_RECOVERY", reason="Company in judicial recovery", blocking=True, severity=5))
    if confirmed_default:
        flags.append(RedFlag(code="CONFIRMED_DEFAULT", reason="Confirmed debt default", blocking=True, severity=5))
    if adverse_auditor_opinion:
        flags.append(RedFlag(code="ADVERSE_AUDITOR_OPINION", reason="Adverse auditor opinion", blocking=True, severity=5))
    if confirmed_accounting_fraud:
        flags.append(RedFlag(code="ACCOUNTING_FRAUD", reason="Confirmed material accounting fraud", blocking=True, severity=5))
    if latest_financial_publication and as_of:
        age = (as_of - latest_financial_publication).days
        if age > max_staleness_days:
            flags.append(RedFlag(code="STALE_FINANCIALS", reason=f"Critical financial data is {age} days old", blocking=False, severity=4))
    return flags
