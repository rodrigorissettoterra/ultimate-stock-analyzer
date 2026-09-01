from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_COMPANY_ID,
    FIGE_FINANCIAL_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.fundamentals.metrics import effective_tax_rate

FIGE_KNOWN_EXTRAORDINARY_DISTRIBUTION_YEARS = frozenset({2022})


@dataclass(frozen=True, slots=True)
class FigeEconomicMetricAssessment:
    metric_group: str
    status: str
    rationale: str


@dataclass(frozen=True, slots=True)
class FigeEconomicYearAudit:
    company_id: str
    fiscal_year: int
    reference_date: date
    values: dict[str, float]
    metrics: dict[str, float | None]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FigeEconomicHistoryAuditReport:
    company_id: str
    start_year: int
    end_year: int
    annual_audits: tuple[FigeEconomicYearAudit, ...]
    historical_statistics: dict[str, float | int | None]
    metric_assessments: tuple[FigeEconomicMetricAssessment, ...]
    warnings: tuple[str, ...]
    scope: str = "DIAGNOSTIC_FIGE_ECONOMIC_METRICS"
    effect: str = "diagnostic_only_not_routed_or_scored"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_fige_economic_year(
    *,
    company_id: str,
    fiscal_year: int,
    reference_date: date,
    values: Mapping[str, float],
    prior_year_values: Mapping[str, float] | None = None,
) -> FigeEconomicYearAudit:
    """Calculate diagnostic FIGE ratios from already validated contract values."""

    if company_id != FIGE_COMPANY_ID:
        raise ValueError(
            "FIGE economic audit company identity mismatch: "
            f"expected={FIGE_COMPANY_ID} actual={company_id}"
        )
    if reference_date.year != fiscal_year:
        raise ValueError(
            "FIGE economic audit fiscal/reference year mismatch: "
            f"fiscal_year={fiscal_year} reference_date={reference_date.isoformat()}"
        )

    raw_values = {key: float(value) for key, value in values.items()}
    warnings: list[str] = []

    total_assets = raw_values.get("total_assets")
    financial_assets = raw_values.get("financial_assets")
    securities = raw_values.get("securities_amortized_cost")
    equity = raw_values.get("equity")
    financial_liabilities = raw_values.get("financial_liabilities_amortized_cost")
    fiscal_liabilities = raw_values.get("fiscal_liabilities")
    intermediation_revenue = raw_values.get("financial_intermediation_revenue")
    intermediation_expense = raw_values.get("financial_intermediation_expense")
    gross_intermediation_result = raw_values.get("gross_financial_intermediation_result")
    other_operating_result = raw_values.get("other_operating_result")
    pretax_income = raw_values.get("pretax_income")
    income_tax = raw_values.get("income_tax")
    continuing_income = raw_values.get("continuing_operations_income")
    net_income = raw_values.get("net_income")

    prior = dict(prior_year_values) if prior_year_values is not None else {}
    average_assets = _positive_average(prior.get("total_assets"), total_assets)
    average_financial_assets = _positive_average(
        prior.get("financial_assets"),
        financial_assets,
    )
    average_equity = _positive_average(prior.get("equity"), equity)

    metrics: dict[str, float | None] = {
        "roe_closing_equity": _positive_ratio(net_income, equity),
        "roe_average_equity": _positive_ratio(net_income, average_equity),
        "roa_closing_assets": _positive_ratio(net_income, total_assets),
        "roa_average_assets": _positive_ratio(net_income, average_assets),
        "net_income_to_closing_financial_assets": _positive_ratio(
            net_income,
            financial_assets,
        ),
        "net_income_to_average_financial_assets": _positive_ratio(
            net_income,
            average_financial_assets,
        ),
        "financial_assets_to_assets": _positive_ratio(financial_assets, total_assets),
        "securities_to_assets": _positive_ratio(securities, total_assets),
        "securities_to_financial_assets": _positive_ratio(
            securities,
            financial_assets,
        ),
        "equity_to_assets": _positive_ratio(equity, total_assets),
        "financial_liabilities_to_assets": _positive_ratio(
            financial_liabilities,
            total_assets,
        ),
        "fiscal_liabilities_to_assets": _positive_ratio(
            fiscal_liabilities,
            total_assets,
        ),
        "gross_intermediation_result_to_closing_assets": _positive_ratio(
            gross_intermediation_result,
            total_assets,
        ),
        "gross_intermediation_result_to_average_assets": _positive_ratio(
            gross_intermediation_result,
            average_assets,
        ),
        "intermediation_expense_to_revenue": _absolute_cost_ratio(
            intermediation_expense,
            intermediation_revenue,
        ),
        "other_operating_result_to_gross_intermediation_result": _positive_base_ratio(
            other_operating_result,
            gross_intermediation_result,
        ),
        "pretax_income_to_gross_intermediation_result": _positive_base_ratio(
            pretax_income,
            gross_intermediation_result,
        ),
        "effective_tax_burden": effective_tax_rate(income_tax, pretax_income),
        "net_income_to_pretax_income": _positive_base_ratio(
            net_income,
            pretax_income,
        ),
        "non_continuing_result_gap_to_abs_net_income": _non_continuing_gap_ratio(
            net_income,
            continuing_income,
        ),
    }
    metrics["roe_denominator_sensitivity"] = _absolute_difference(
        metrics["roe_closing_equity"],
        metrics["roe_average_equity"],
    )
    metrics["roa_denominator_sensitivity"] = _absolute_difference(
        metrics["roa_closing_assets"],
        metrics["roa_average_assets"],
    )
    metrics["financial_asset_return_denominator_sensitivity"] = _absolute_difference(
        metrics["net_income_to_closing_financial_assets"],
        metrics["net_income_to_average_financial_assets"],
    )

    _append_missing_input_warnings(raw_values, warnings)

    if prior_year_values is None:
        warnings.append("NO_PRIOR_YEAR_FOR_AVERAGE_DENOMINATORS")
    if fiscal_year in FIGE_KNOWN_EXTRAORDINARY_DISTRIBUTION_YEARS:
        warnings.append("KNOWN_EXTRAORDINARY_DISTRIBUTION_AFFECTS_EQUITY_COMPARABILITY")
    if metrics["roe_average_equity"] is None:
        warnings.append("ROE_AVERAGE_DENOMINATOR_UNAVAILABLE")
    if metrics["roa_average_assets"] is None:
        warnings.append("ROA_AVERAGE_DENOMINATOR_UNAVAILABLE")
    if metrics["net_income_to_average_financial_assets"] is None:
        warnings.append("FINANCIAL_ASSET_RETURN_AVERAGE_DENOMINATOR_UNAVAILABLE")

    return FigeEconomicYearAudit(
        company_id=company_id,
        fiscal_year=fiscal_year,
        reference_date=reference_date,
        values=raw_values,
        metrics=metrics,
        warnings=tuple(sorted(set(warnings))),
    )


def audit_fige_economic_history(
    annual_audits: Sequence[FigeEconomicYearAudit],
) -> FigeEconomicHistoryAuditReport:
    """Summarize multi-year FIGE diagnostics without assigning score weights."""

    if not annual_audits:
        raise ValueError("FIGE economic history audit requires at least one year")

    ordered = tuple(sorted(annual_audits, key=lambda item: item.fiscal_year))
    if any(item.company_id != FIGE_COMPANY_ID for item in ordered):
        raise ValueError("FIGE economic history audit contains another company identity")

    fiscal_years = tuple(item.fiscal_year for item in ordered)
    if len(set(fiscal_years)) != len(fiscal_years):
        raise ValueError("FIGE economic history audit contains duplicate fiscal years")
    if fiscal_years != tuple(range(fiscal_years[0], fiscal_years[-1] + 1)):
        raise ValueError("FIGE economic history audit requires contiguous fiscal years")

    net_income_series = [item.values.get("net_income") for item in ordered]
    historical_statistics: dict[str, float | int | None] = {
        "year_count": len(ordered),
        "positive_net_income_year_ratio": _positive_observation_ratio(net_income_series),
        "net_income_mean": _mean(net_income_series),
        "net_income_population_stdev": _population_stdev(net_income_series),
        "net_income_coefficient_of_variation": _coefficient_of_variation(
            net_income_series
        ),
        "roe_closing_equity_population_stdev": _metric_stdev(
            ordered,
            "roe_closing_equity",
        ),
        "roe_average_equity_population_stdev": _metric_stdev(
            ordered,
            "roe_average_equity",
        ),
        "roa_closing_assets_population_stdev": _metric_stdev(
            ordered,
            "roa_closing_assets",
        ),
        "roa_average_assets_population_stdev": _metric_stdev(
            ordered,
            "roa_average_assets",
        ),
        "financial_assets_to_assets_min": _metric_min(
            ordered,
            "financial_assets_to_assets",
        ),
        "financial_assets_to_assets_max": _metric_max(
            ordered,
            "financial_assets_to_assets",
        ),
        "equity_to_assets_min": _metric_min(ordered, "equity_to_assets"),
        "equity_to_assets_max": _metric_max(ordered, "equity_to_assets"),
        "financial_liabilities_to_assets_max": _metric_max(
            ordered,
            "financial_liabilities_to_assets",
        ),
        "non_continuing_result_gap_to_abs_net_income_max": _metric_max(
            ordered,
            "non_continuing_result_gap_to_abs_net_income",
        ),
    }

    assessments = (
        FigeEconomicMetricAssessment(
            metric_group="profitability",
            status="AUDITABLE_CANDIDATE",
            rationale=(
                "ROE, ROA and profit-to-financial-assets are economically aligned with "
                "FIGE, but average-denominator variants and sensitivity must be reviewed."
            ),
        ),
        FigeEconomicMetricAssessment(
            metric_group="balance_sheet_structure",
            status="AUDITABLE_CANDIDATE",
            rationale=(
                "Financial-asset concentration, equity/assets and financial-liability "
                "intensity use semantically stable FIGE balance-sheet accounts."
            ),
        ),
        FigeEconomicMetricAssessment(
            metric_group="result_composition",
            status="AUDITABLE_CANDIDATE",
            rationale=(
                "Intermediation cost, gross-result retention, tax burden and continuing-"
                "operations reconciliation can be derived from FIGE-specific DRE accounts."
            ),
        ),
        FigeEconomicMetricAssessment(
            metric_group="profit_stability",
            status="DESCRIPTIVE_ONLY",
            rationale=(
                "Five annual observations are sufficient for descriptive stability and "
                "volatility evidence, not for a standalone normative score threshold."
            ),
        ),
        FigeEconomicMetricAssessment(
            metric_group="balance_growth_quality",
            status="BLOCKED_WITH_CURRENT_CONTRACT",
            rationale=(
                "The current contract does not normalize DMPL/capital distributions; the "
                "known 2022 extraordinary distribution makes raw balance growth misleading."
            ),
        ),
        FigeEconomicMetricAssessment(
            metric_group="dividend_sustainability",
            status="BLOCKED_WITH_CURRENT_CONTRACT",
            rationale=(
                "Dividend sustainability requires a dedicated distribution/DMPL contract "
                "before FIGE payouts can be separated from extraordinary reserve releases."
            ),
        ),
    )

    warnings = (
        "NO_SCORING_OR_ROUTING_CHANGE_IN_THIS_AUDIT",
        "BALANCE_GROWTH_IS_NOT_ECONOMIC_QUALITY_EVIDENCE_WITHOUT_DISTRIBUTION_CONTRACT",
        "LATEST_ANNUAL_CVM_ARCHIVES_ARE_NOT_STRICT_REVISION_HISTORY_PIT_EVIDENCE",
    )
    return FigeEconomicHistoryAuditReport(
        company_id=FIGE_COMPANY_ID,
        start_year=fiscal_years[0],
        end_year=fiscal_years[-1],
        annual_audits=ordered,
        historical_statistics=historical_statistics,
        metric_assessments=assessments,
        warnings=warnings,
    )


def _positive_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _positive_base_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    return _positive_ratio(numerator, denominator)


def _absolute_cost_ratio(
    expense: float | None,
    revenue: float | None,
) -> float | None:
    if expense is None:
        return None
    return _positive_ratio(abs(expense), revenue)


def _non_continuing_gap_ratio(
    net_income: float | None,
    continuing_income: float | None,
) -> float | None:
    if net_income is None or continuing_income is None or net_income == 0:
        return None
    return abs(net_income - continuing_income) / abs(net_income)


def _positive_average(
    prior: float | None,
    current: float | None,
) -> float | None:
    if prior is None or current is None or prior <= 0 or current <= 0:
        return None
    return (prior + current) / 2


def _absolute_difference(
    first: float | None,
    second: float | None,
) -> float | None:
    if first is None or second is None:
        return None
    return abs(first - second)


def _append_missing_input_warnings(
    values: Mapping[str, float],
    warnings: list[str],
) -> None:
    expected_inputs = tuple(
        binding.concept_id for binding in FIGE_FINANCIAL_ACCOUNT_BINDINGS
    )
    for concept_id in expected_inputs:
        if concept_id not in values:
            warnings.append(f"UNKNOWN_INPUT:{concept_id}")


def _known(values: Sequence[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None and math.isfinite(value)]


def _mean(values: Sequence[float | None]) -> float | None:
    known = _known(values)
    return statistics.fmean(known) if known else None


def _population_stdev(values: Sequence[float | None]) -> float | None:
    known = _known(values)
    if not known:
        return None
    return statistics.pstdev(known)


def _coefficient_of_variation(values: Sequence[float | None]) -> float | None:
    known = _known(values)
    if not known:
        return None
    mean_value = statistics.fmean(known)
    if mean_value == 0:
        return None
    return statistics.pstdev(known) / abs(mean_value)


def _positive_observation_ratio(values: Sequence[float | None]) -> float | None:
    known = _known(values)
    if not known:
        return None
    return sum(value > 0 for value in known) / len(known)


def _metric_values(
    audits: Sequence[FigeEconomicYearAudit],
    metric_id: str,
) -> list[float | None]:
    return [audit.metrics.get(metric_id) for audit in audits]


def _metric_stdev(
    audits: Sequence[FigeEconomicYearAudit],
    metric_id: str,
) -> float | None:
    return _population_stdev(_metric_values(audits, metric_id))


def _metric_min(
    audits: Sequence[FigeEconomicYearAudit],
    metric_id: str,
) -> float | None:
    known = _known(_metric_values(audits, metric_id))
    return min(known) if known else None


def _metric_max(
    audits: Sequence[FigeEconomicYearAudit],
    metric_id: str,
) -> float | None:
    known = _known(_metric_values(audits, metric_id))
    return max(known) if known else None
