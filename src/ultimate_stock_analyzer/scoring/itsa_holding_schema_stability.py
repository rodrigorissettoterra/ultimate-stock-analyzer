from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.fundamentals.metrics import safe_div
from ultimate_stock_analyzer.scoring.statement_schema_stability import (
    STATUS_STABLE_EXACT,
    StatementSchemaCandidate,
    StatementSchemaStabilityReport,
    audit_statement_schema_stability,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

ITSA_COMPANY_ID = "cvm:7617"
ITSA_CVM_CODE = 7617
ITSA_BASELINE_YEAR = 2025


@dataclass(frozen=True, slots=True)
class ItsaHoldingSchemaCode:
    concept_id: str
    statement: str
    account_code: str
    tier: str = "supporting"


ITSA_HOLDING_SCHEMA_CODES = (
    ItsaHoldingSchemaCode("total_assets", "BPA", "1", tier="core"),
    ItsaHoldingSchemaCode(
        "investments_total",
        "BPA",
        "1.02.02",
        tier="core",
    ),
    ItsaHoldingSchemaCode(
        "equity_investments",
        "BPA",
        "1.02.02.01",
    ),
    ItsaHoldingSchemaCode(
        "other_investments",
        "BPA",
        "1.02.02.01.04",
    ),
    ItsaHoldingSchemaCode("equity", "BPP", "2.03", tier="core"),
    ItsaHoldingSchemaCode(
        "equity_method_result",
        "DRE",
        "3.04.06",
        tier="core",
    ),
    ItsaHoldingSchemaCode(
        "net_income_parent",
        "DRE",
        "3.11.01",
        tier="core",
    ),
)


@dataclass(frozen=True, slots=True)
class ItsaHoldingYearEvidence:
    fiscal_year: int
    reference_date: date | None
    total_assets: float | None
    investments_total: float | None
    equity_investments: float | None
    other_investments: float | None
    equity: float | None
    equity_method_result: float | None
    net_income_parent: float | None
    investments_to_assets: float | None
    equity_to_assets: float | None
    equity_method_to_net_income: float | None
    equity_investments_to_investments: float | None
    other_investments_to_investments: float | None


@dataclass(frozen=True, slots=True)
class ItsaHoldingSchemaStabilityAuditReport:
    company_id: str
    baseline_year: int
    candidates: tuple[StatementSchemaCandidate, ...]
    schema_stability: StatementSchemaStabilityReport
    year_evidence: tuple[ItsaHoldingYearEvidence, ...]
    all_core_schema_stable: bool
    scope: str = "DIAGNOSTIC_ITSA_HOLDING_SCHEMA_STABILITY"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_itsa_holding_schema_stability(
    reports_by_year: dict[int, FinancialStatementTreeAuditReport],
    *,
    start_year: int,
    end_year: int,
    baseline_year: int = ITSA_BASELINE_YEAR,
) -> ItsaHoldingSchemaStabilityAuditReport:
    """Audit exact ITSA holding-account schema and economic context across DFP years.

    Account codes are the explicit candidates identified by the prior 2025 holding
    diagnostic. Labels are never guessed: the baseline label for every candidate is
    read from the exact 2025 statement tree and then compared across the requested
    annual window.
    """

    if start_year > end_year:
        raise ValueError("start_year must not be greater than end_year")
    if baseline_year < start_year or baseline_year > end_year:
        raise ValueError("baseline_year must be inside the requested audit window")

    baseline = reports_by_year.get(baseline_year)
    if baseline is None:
        raise ValueError(f"missing ITSA baseline report for year={baseline_year}")
    if baseline.company_id != ITSA_COMPANY_ID:
        raise ValueError(
            "ITSA baseline report company identity mismatch: "
            f"expected={ITSA_COMPANY_ID} actual={baseline.company_id}"
        )
    if baseline.reference_date is not None and baseline.reference_date.year != baseline_year:
        raise ValueError(
            "ITSA baseline report reference year mismatch: "
            f"expected={baseline_year} actual={baseline.reference_date.year}"
        )

    candidates = tuple(
        _candidate_from_baseline(baseline, code)
        for code in ITSA_HOLDING_SCHEMA_CODES
    )
    stability = audit_statement_schema_stability(
        reports_by_year,
        company_id=ITSA_COMPANY_ID,
        candidates=candidates,
        start_year=start_year,
        end_year=end_year,
    )
    all_core_stable = all(
        result.status == STATUS_STABLE_EXACT
        for result in stability.results
        if result.tier == "core"
    )
    year_evidence = tuple(
        _year_evidence(year, reports_by_year.get(year))
        for year in range(start_year, end_year + 1)
    )

    return ItsaHoldingSchemaStabilityAuditReport(
        company_id=ITSA_COMPANY_ID,
        baseline_year=baseline_year,
        candidates=candidates,
        schema_stability=stability,
        year_evidence=year_evidence,
        all_core_schema_stable=all_core_stable,
    )


def _candidate_from_baseline(
    baseline: FinancialStatementTreeAuditReport,
    code: ItsaHoldingSchemaCode,
) -> StatementSchemaCandidate:
    matching = [
        line
        for line in baseline.lines
        if line.statement == code.statement
        and line.account_code == code.account_code
    ]
    if len(matching) != 1:
        raise ValueError(
            "ITSA baseline schema code must resolve exactly once: "
            f"statement={code.statement} account_code={code.account_code} "
            f"matches={len(matching)}"
        )
    line = matching[0]
    return StatementSchemaCandidate(
        concept_id=code.concept_id,
        statement=code.statement,
        account_code=code.account_code,
        baseline_label=line.account_name,
        tier=code.tier,
    )


def _year_evidence(
    fiscal_year: int,
    report: FinancialStatementTreeAuditReport | None,
) -> ItsaHoldingYearEvidence:
    total_assets = _exact_value(report, "BPA", "1")
    investments_total = _exact_value(report, "BPA", "1.02.02")
    equity_investments = _exact_value(report, "BPA", "1.02.02.01")
    other_investments = _exact_value(report, "BPA", "1.02.02.01.04")
    equity = _exact_value(report, "BPP", "2.03")
    equity_method_result = _exact_value(report, "DRE", "3.04.06")
    net_income_parent = _exact_value(report, "DRE", "3.11.01")

    return ItsaHoldingYearEvidence(
        fiscal_year=fiscal_year,
        reference_date=report.reference_date if report is not None else None,
        total_assets=total_assets,
        investments_total=investments_total,
        equity_investments=equity_investments,
        other_investments=other_investments,
        equity=equity,
        equity_method_result=equity_method_result,
        net_income_parent=net_income_parent,
        investments_to_assets=safe_div(investments_total, total_assets),
        equity_to_assets=safe_div(equity, total_assets),
        equity_method_to_net_income=safe_div(
            equity_method_result,
            net_income_parent,
        ),
        equity_investments_to_investments=safe_div(
            equity_investments,
            investments_total,
        ),
        other_investments_to_investments=safe_div(
            other_investments,
            investments_total,
        ),
    )


def _exact_value(
    report: FinancialStatementTreeAuditReport | None,
    statement: str,
    account_code: str,
) -> float | None:
    if report is None:
        return None
    if report.company_id != ITSA_COMPANY_ID:
        raise ValueError(
            "ITSA year-evidence company identity mismatch: "
            f"expected={ITSA_COMPANY_ID} actual={report.company_id}"
        )
    matching = [
        line
        for line in report.lines
        if line.statement == statement
        and line.account_code == account_code
    ]
    if len(matching) > 1:
        raise ValueError(
            "ambiguous ITSA exact account after statement-tree normalization: "
            f"statement={statement} account_code={account_code} "
            f"matches={len(matching)}"
        )
    return matching[0].value_brl if matching else None
