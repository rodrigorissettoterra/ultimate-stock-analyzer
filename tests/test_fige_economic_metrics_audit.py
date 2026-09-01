from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.fundamentals.fige_economic_metrics_audit import (
    audit_fige_economic_history,
    audit_fige_economic_year,
)


def _values(**overrides: float) -> dict[str, float]:
    values = {
        "total_assets": 200.0,
        "cash_and_equivalents": 4.0,
        "financial_assets": 196.0,
        "securities_amortized_cost": 190.0,
        "financial_liabilities_amortized_cost": 0.0,
        "provisions": 2.0,
        "fiscal_liabilities": 5.0,
        "equity": 190.0,
        "financial_intermediation_revenue": 25.0,
        "financial_intermediation_expense": -4.0,
        "gross_financial_intermediation_result": 21.0,
        "other_operating_result": -3.0,
        "pretax_income": 18.0,
        "income_tax": -3.0,
        "continuing_operations_income": 15.0,
        "net_income": 15.0,
    }
    values.update(overrides)
    return values


def _annual(
    year: int,
    *,
    values: dict[str, float] | None = None,
    prior_values: dict[str, float] | None = None,
):
    return audit_fige_economic_year(
        company_id="cvm:6041",
        fiscal_year=year,
        reference_date=date(year, 12, 31),
        values=values or _values(),
        prior_year_values=prior_values,
    )


def test_fige_economic_year_calculates_financial_profile_ratios() -> None:
    prior = _values(total_assets=180.0, financial_assets=175.0, equity=170.0)
    audit = _annual(2025, prior_values=prior)

    assert audit.metrics["roe_closing_equity"] == pytest.approx(15.0 / 190.0)
    assert audit.metrics["roe_average_equity"] == pytest.approx(15.0 / 180.0)
    assert audit.metrics["roa_closing_assets"] == pytest.approx(15.0 / 200.0)
    assert audit.metrics["roa_average_assets"] == pytest.approx(15.0 / 190.0)
    assert audit.metrics["financial_assets_to_assets"] == pytest.approx(0.98)
    assert audit.metrics["securities_to_assets"] == pytest.approx(0.95)
    assert audit.metrics["equity_to_assets"] == pytest.approx(0.95)
    assert audit.metrics["effective_tax_burden"] == pytest.approx(3.0 / 18.0)
    assert audit.metrics["non_continuing_result_gap_to_abs_net_income"] == 0.0


def test_fige_economic_year_preserves_reported_zero_as_known_ratio() -> None:
    audit = _annual(2025, prior_values=_values())

    assert audit.metrics["financial_liabilities_to_assets"] == 0.0


def test_fige_economic_year_keeps_missing_input_unknown() -> None:
    values = _values()
    values.pop("fiscal_liabilities")

    audit = _annual(2025, values=values, prior_values=_values())

    assert audit.metrics["fiscal_liabilities_to_assets"] is None
    assert "UNKNOWN_INPUT:fiscal_liabilities" in audit.warnings


def test_fige_economic_year_requires_positive_balance_denominators() -> None:
    audit = _annual(
        2025,
        values=_values(total_assets=0.0, equity=0.0, financial_assets=0.0),
        prior_values=_values(),
    )

    assert audit.metrics["roe_closing_equity"] is None
    assert audit.metrics["roa_closing_assets"] is None
    assert audit.metrics["net_income_to_closing_financial_assets"] is None


def test_fige_economic_year_keeps_first_year_average_denominators_unknown() -> None:
    audit = _annual(2021)

    assert audit.metrics["roe_average_equity"] is None
    assert audit.metrics["roa_average_assets"] is None
    assert audit.metrics["net_income_to_average_financial_assets"] is None
    assert "NO_PRIOR_YEAR_FOR_AVERAGE_DENOMINATORS" in audit.warnings


def test_fige_economic_year_flags_known_2022_extraordinary_distribution() -> None:
    audit = _annual(2022, prior_values=_values())

    assert (
        "KNOWN_EXTRAORDINARY_DISTRIBUTION_AFFECTS_EQUITY_COMPARABILITY"
        in audit.warnings
    )


def test_fige_economic_audit_rejects_other_company_identity() -> None:
    with pytest.raises(ValueError, match="company identity mismatch"):
        audit_fige_economic_year(
            company_id="cvm:9999",
            fiscal_year=2025,
            reference_date=date(2025, 12, 31),
            values=_values(),
            prior_year_values=_values(),
        )


def test_fige_economic_history_is_diagnostic_and_blocks_unsupported_groups() -> None:
    audits = []
    prior = None
    for year, net_income in (
        (2021, 10.0),
        (2022, 12.0),
        (2023, 14.0),
        (2024, 13.0),
        (2025, 15.0),
    ):
        current = _values(net_income=net_income, continuing_operations_income=net_income)
        audits.append(_annual(year, values=current, prior_values=prior))
        prior = current

    report = audit_fige_economic_history(audits)
    statuses = {
        assessment.metric_group: assessment.status
        for assessment in report.metric_assessments
    }

    assert report.effect == "diagnostic_only_not_routed_or_scored"
    assert report.point_in_time_eligible is False
    assert report.historical_statistics["year_count"] == 5
    assert report.historical_statistics["positive_net_income_year_ratio"] == 1.0
    assert statuses["profitability"] == "AUDITABLE_CANDIDATE"
    assert statuses["balance_growth_quality"] == "BLOCKED_WITH_CURRENT_CONTRACT"
    assert statuses["dividend_sustainability"] == "BLOCKED_WITH_CURRENT_CONTRACT"


def test_fige_economic_history_requires_contiguous_unique_years() -> None:
    with pytest.raises(ValueError, match="contiguous fiscal years"):
        audit_fige_economic_history((_annual(2021), _annual(2023)))

    with pytest.raises(ValueError, match="duplicate fiscal years"):
        audit_fige_economic_history((_annual(2021), _annual(2021)))
