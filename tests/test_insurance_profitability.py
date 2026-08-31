import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_profitability import (
    derive_susep_profitability_metrics,
    insurance_profitability_features,
)


def _table(*, net_income: float = 20.0) -> pd.DataFrame:
    rows = [
        {"coenti": 12345, "damesano": 202512, "cmpid": 518, "valor": net_income},
        {"coenti": 12345, "damesano": 202512, "cmpid": 3333, "valor": 120.0},
        {"coenti": 12345, "damesano": 202412, "cmpid": 3333, "valor": 80.0},
        {"coenti": 12345, "damesano": 202512, "cmpid": 1039, "valor": 600.0},
        {"coenti": 12345, "damesano": 202412, "cmpid": 1039, "valor": 400.0},
        {"coenti": 99999, "damesano": 202512, "cmpid": 518, "valor": 999.0},
    ]
    historical_income = {2020: 10.0, 2021: 11.0, 2022: 12.0, 2023: 14.0, 2024: 16.0}
    rows.extend(
        {"coenti": 12345, "damesano": year * 100 + 12, "cmpid": 518, "valor": value}
        for year, value in historical_income.items()
    )
    return pd.DataFrame(rows)


def test_profitability_uses_december_ytd_average_balances_and_strict_growth() -> None:
    metrics = derive_susep_profitability_metrics(
        _table(), susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.net_income == pytest.approx(20.0)
    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa == pytest.approx(0.04)
    assert metrics.net_income_cagr_5y == pytest.approx((20.0 / 10.0) ** (1 / 5) - 1)
    assert metrics.point_in_time_eligible is False
    features = insurance_profitability_features(
        _table(), susep_company_code="12345", fiscal_year=2025
    )
    assert features["roe"] == pytest.approx(0.20)
    assert features["roa"] == pytest.approx(0.04)
    assert features["net_income_cagr_5y"] == pytest.approx((20.0 / 10.0) ** (1 / 5) - 1)


def test_profitability_allows_negative_net_income_but_growth_fails_closed() -> None:
    metrics = derive_susep_profitability_metrics(
        _table(net_income=-10.0), susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe == pytest.approx(-0.10)
    assert metrics.roa == pytest.approx(-0.02)
    assert metrics.net_income_cagr_5y is None


def test_growth_requires_all_six_consecutive_december_observations() -> None:
    table = _table()
    table = table.loc[~((table["damesano"] == 202212) & (table["cmpid"] == 518))].copy()

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa == pytest.approx(0.04)
    assert metrics.net_income_cagr_5y is None


def test_growth_requires_positive_endpoints_and_nonnegative_intermediate_history() -> None:
    endpoint_table = _table()
    endpoint_table.loc[
        (endpoint_table["damesano"] == 202012) & (endpoint_table["cmpid"] == 518), "valor"
    ] = 0.0
    intermediate_table = _table()
    intermediate_table.loc[
        (intermediate_table["damesano"] == 202212)
        & (intermediate_table["cmpid"] == 518),
        "valor",
    ] = -1.0

    endpoint_metrics = derive_susep_profitability_metrics(
        endpoint_table, susep_company_code="12345", fiscal_year=2025
    )
    intermediate_metrics = derive_susep_profitability_metrics(
        intermediate_table, susep_company_code="12345", fiscal_year=2025
    )

    assert endpoint_metrics.net_income_cagr_5y is None
    assert intermediate_metrics.net_income_cagr_5y is None


def test_duplicate_net_income_fails_roe_roa_and_growth_closed() -> None:
    table = pd.concat(
        [
            _table(),
            pd.DataFrame(
                [{"coenti": 12345, "damesano": 202512, "cmpid": 518, "valor": 20.0}]
            ),
        ],
        ignore_index=True,
    )

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.net_income is None
    assert metrics.roe is None
    assert metrics.roa is None
    assert metrics.net_income_cagr_5y is None


def test_missing_prior_equity_only_blocks_roe() -> None:
    table = _table()
    table = table.loc[
        ~((table["damesano"] == 202412) & (table["cmpid"] == 3333))
    ].copy()

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe is None
    assert metrics.roa == pytest.approx(0.04)
    assert metrics.net_income_cagr_5y is not None


def test_missing_prior_assets_only_blocks_roa() -> None:
    table = _table()
    table = table.loc[
        ~((table["damesano"] == 202412) & (table["cmpid"] == 1039))
    ].copy()

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa is None


def test_nonpositive_average_denominator_fails_closed() -> None:
    table = _table()
    table.loc[
        (table["damesano"] == 202512) & (table["cmpid"] == 3333), "valor"
    ] = -120.0
    table.loc[
        (table["damesano"] == 202412) & (table["cmpid"] == 3333), "valor"
    ] = 80.0

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe is None
    assert metrics.roa == pytest.approx(0.04)


def test_nonnumeric_value_fails_only_dependent_metric() -> None:
    table = _table().astype({"valor": "object"})
    table.loc[
        (table["damesano"] == 202512) & (table["cmpid"] == 1039), "valor"
    ] = "UNKNOWN"

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa is None


def test_wrong_company_and_pre_contract_year_are_unknown() -> None:
    wrong_company = derive_susep_profitability_metrics(
        _table(), susep_company_code="54321", fiscal_year=2025
    )
    old_year = derive_susep_profitability_metrics(
        _table(), susep_company_code="12345", fiscal_year=2013
    )

    assert wrong_company.roe is None
    assert wrong_company.roa is None
    assert wrong_company.net_income_cagr_5y is None
    assert old_year.roe is None
    assert old_year.roa is None
    assert old_year.net_income_cagr_5y is None


def test_company_code_must_be_numeric() -> None:
    with pytest.raises(ValueError, match="only digits"):
        derive_susep_profitability_metrics(
            _table(), susep_company_code="ABC", fiscal_year=2025
        )


def test_required_schema_is_enforced() -> None:
    with pytest.raises(ValueError, match="cmpid"):
        derive_susep_profitability_metrics(
            pd.DataFrame([{"coenti": 12345, "damesano": 202512, "valor": 1.0}]),
            susep_company_code="12345",
            fiscal_year=2025,
        )
