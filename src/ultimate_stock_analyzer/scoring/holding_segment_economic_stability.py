from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median

from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_HOLDING_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.fundamentals.metrics import safe_div
from ultimate_stock_analyzer.scoring.itsa_peer_discovery import (
    compare_itsa_holding_schema,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)


@dataclass(frozen=True, slots=True)
class HoldingSegmentMember:
    company_id: str
    cvm_code: int
    issuer_code: str
    trading_name: str
    sector: str
    subsector: str
    segment: str
    model_id: str


@dataclass(frozen=True, slots=True)
class HoldingSegmentYearEvidence:
    company_id: str
    fiscal_year: int
    reference_date: str | None
    statement_evidence_present: bool
    critical_schema_coverage: float
    total_schema_coverage: float
    exact_schema_match: bool
    exact_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    label_mismatch_concepts: tuple[str, ...]
    ambiguous_concepts: tuple[str, ...]
    values: dict[str, float]
    descriptive_metrics: dict[str, float | None]


@dataclass(frozen=True, slots=True)
class MetricRange:
    observations: int
    minimum: float | None
    maximum: float | None
    median: float | None


@dataclass(frozen=True, slots=True)
class HoldingSegmentCompanySummary:
    company_id: str
    issuer_code: str
    trading_name: str
    model_id: str
    statement_evidence_years: tuple[int, ...]
    missing_statement_years: tuple[int, ...]
    critical_schema_complete_years: tuple[int, ...]
    full_schema_exact_years: tuple[int, ...]
    critical_schema_complete_all_observed_years: bool
    metric_ranges: dict[str, MetricRange]


@dataclass(frozen=True, slots=True)
class HoldingSegmentEconomicStabilityReport:
    anchor_company_id: str
    sector: str
    subsector: str
    segment: str
    start_year: int
    end_year: int
    member_count: int
    members: tuple[HoldingSegmentMember, ...]
    year_evidence: tuple[HoldingSegmentYearEvidence, ...]
    company_summaries: tuple[HoldingSegmentCompanySummary, ...]
    all_members_have_statement_evidence: bool
    all_members_critical_schema_complete_all_observed_years: bool
    segment_routing_ready: bool = False
    applicability_registry_resolvable: bool = False
    scope: str = "DIAGNOSTIC_HOLDING_SEGMENT_ECONOMIC_STABILITY"
    effect: str = "diagnostic_only_no_routing_or_scoring"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_holding_segment_economic_stability(
    *,
    members: tuple[HoldingSegmentMember, ...],
    reports_by_company_year: dict[
        tuple[str, int], FinancialStatementTreeAuditReport
    ],
    anchor_company_id: str,
    start_year: int,
    end_year: int,
) -> HoldingSegmentEconomicStabilityReport:
    if start_year > end_year:
        raise ValueError("start_year must not be greater than end_year")
    if not members:
        raise ValueError("holding-segment audit requires at least one member")

    by_id = {member.company_id: member for member in members}
    if len(by_id) != len(members):
        raise ValueError("holding-segment member company ids must be unique")
    if anchor_company_id not in by_id:
        raise ValueError("holding-segment anchor must be present in members")

    anchor = by_id[anchor_company_id]
    for member in members:
        if (
            _text_key(member.sector),
            _text_key(member.subsector),
            _text_key(member.segment),
        ) != (
            _text_key(anchor.sector),
            _text_key(anchor.subsector),
            _text_key(anchor.segment),
        ):
            raise ValueError(
                "holding-segment members must share the anchor exact B3 classification"
            )

    evidence_rows: list[HoldingSegmentYearEvidence] = []
    years = tuple(range(start_year, end_year + 1))
    for member in sorted(members, key=lambda item: (item.issuer_code, item.company_id)):
        for fiscal_year in years:
            report = reports_by_company_year.get((member.company_id, fiscal_year))
            evidence_rows.append(
                _year_evidence(
                    member.company_id,
                    fiscal_year,
                    report,
                )
            )

    evidence_tuple = tuple(evidence_rows)
    summaries = tuple(
        _company_summary(member, years, evidence_tuple)
        for member in sorted(members, key=lambda item: (item.issuer_code, item.company_id))
    )
    return HoldingSegmentEconomicStabilityReport(
        anchor_company_id=anchor_company_id,
        sector=anchor.sector,
        subsector=anchor.subsector,
        segment=anchor.segment,
        start_year=start_year,
        end_year=end_year,
        member_count=len(members),
        members=tuple(sorted(members, key=lambda item: (item.issuer_code, item.company_id))),
        year_evidence=evidence_tuple,
        company_summaries=summaries,
        all_members_have_statement_evidence=all(
            not summary.missing_statement_years for summary in summaries
        ),
        all_members_critical_schema_complete_all_observed_years=all(
            summary.critical_schema_complete_all_observed_years
            for summary in summaries
        ),
    )


def _year_evidence(
    company_id: str,
    fiscal_year: int,
    report: FinancialStatementTreeAuditReport | None,
) -> HoldingSegmentYearEvidence:
    if report is None or not report.lines:
        return HoldingSegmentYearEvidence(
            company_id=company_id,
            fiscal_year=fiscal_year,
            reference_date=(
                report.reference_date.isoformat()
                if report is not None and report.reference_date is not None
                else None
            ),
            statement_evidence_present=False,
            critical_schema_coverage=0.0,
            total_schema_coverage=0.0,
            exact_schema_match=False,
            exact_concepts=(),
            missing_concepts=tuple(
                sorted(binding.concept_id for binding in ITSA_HOLDING_ACCOUNT_BINDINGS)
            ),
            label_mismatch_concepts=(),
            ambiguous_concepts=(),
            values={},
            descriptive_metrics=_descriptive_metrics({}),
        )
    if report.company_id != company_id:
        raise ValueError(
            "holding-segment statement report identity mismatch: "
            f"expected={company_id} actual={report.company_id} year={fiscal_year}"
        )

    schema = compare_itsa_holding_schema(report)
    values = _exact_schema_values(report)
    return HoldingSegmentYearEvidence(
        company_id=company_id,
        fiscal_year=fiscal_year,
        reference_date=(
            report.reference_date.isoformat() if report.reference_date is not None else None
        ),
        statement_evidence_present=True,
        critical_schema_coverage=schema.critical_schema_coverage,
        total_schema_coverage=schema.total_schema_coverage,
        exact_schema_match=schema.exact_schema_match,
        exact_concepts=schema.exact_concepts,
        missing_concepts=schema.missing_concepts,
        label_mismatch_concepts=schema.label_mismatch_concepts,
        ambiguous_concepts=schema.ambiguous_concepts,
        values=values,
        descriptive_metrics=_descriptive_metrics(values),
    )


def _exact_schema_values(
    report: FinancialStatementTreeAuditReport,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for binding in ITSA_HOLDING_ACCOUNT_BINDINGS:
        matching = [
            line
            for line in report.lines
            if line.statement == binding.statement
            and line.account_code == binding.account_code
        ]
        if len(matching) != 1:
            continue
        line = matching[0]
        if _normalize_label(line.account_name) != _normalize_label(binding.expected_label):
            continue
        values[binding.concept_id] = float(line.value_brl)
    return values


def _descriptive_metrics(values: dict[str, float]) -> dict[str, float | None]:
    investments = values.get("investments_total")
    total_assets = values.get("total_assets")
    equity = values.get("equity")
    equity_method_result = values.get("equity_method_result")
    net_income = values.get("net_income_parent")
    equity_investments = values.get("equity_investments")
    other_investments = values.get("other_investments")
    return {
        "investments_to_assets": safe_div(investments, total_assets),
        "equity_to_assets": safe_div(equity, total_assets),
        "equity_method_to_net_income": safe_div(equity_method_result, net_income),
        "equity_investments_to_investments": safe_div(
            equity_investments,
            investments,
        ),
        "other_investments_to_investments": safe_div(
            other_investments,
            investments,
        ),
    }


def _company_summary(
    member: HoldingSegmentMember,
    years: tuple[int, ...],
    evidence: tuple[HoldingSegmentYearEvidence, ...],
) -> HoldingSegmentCompanySummary:
    rows = tuple(row for row in evidence if row.company_id == member.company_id)
    present = tuple(row.fiscal_year for row in rows if row.statement_evidence_present)
    missing = tuple(year for year in years if year not in present)
    critical_complete = tuple(
        row.fiscal_year
        for row in rows
        if row.statement_evidence_present and row.critical_schema_coverage == 1.0
    )
    full_exact = tuple(
        row.fiscal_year for row in rows if row.statement_evidence_present and row.exact_schema_match
    )
    metric_names = tuple(_descriptive_metrics({}).keys())
    ranges = {
        name: _metric_range(
            tuple(
                row.descriptive_metrics[name]
                for row in rows
                if row.descriptive_metrics[name] is not None
            )
        )
        for name in metric_names
    }
    return HoldingSegmentCompanySummary(
        company_id=member.company_id,
        issuer_code=member.issuer_code,
        trading_name=member.trading_name,
        model_id=member.model_id,
        statement_evidence_years=present,
        missing_statement_years=missing,
        critical_schema_complete_years=critical_complete,
        full_schema_exact_years=full_exact,
        critical_schema_complete_all_observed_years=(
            bool(present) and len(critical_complete) == len(present)
        ),
        metric_ranges=ranges,
    )


def _metric_range(values: tuple[float, ...]) -> MetricRange:
    if not values:
        return MetricRange(observations=0, minimum=None, maximum=None, median=None)
    return MetricRange(
        observations=len(values),
        minimum=min(values),
        maximum=max(values),
        median=float(median(values)),
    )


def _normalize_label(value: str) -> str:
    return " ".join(str(value).split())


def _text_key(value: str) -> str:
    return " ".join(str(value).split()).casefold()
