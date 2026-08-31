import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_profitability import (
    derive_susep_profitability_metrics,
    insurance_profitability_features,
)


def _table(*, net_income: float = 20.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"coenti": 12345, "damesano": 202512, "cmpid": 518, "valor": net_income},
            {"coenti": 12345, "damesano": 202512, "cmpid": 3333, "valor": 120.0},
            {"coenti": 12345, "damesano": 202412, "cmpid": 3333, "valor": 80.0},
            {"coenti": 12345, "damesano": 202512, "cmpid": 1039, "valor": 600.0},
            {"coenti": 12345, "damesano": 202412, "cmpid": 1039, "valor": 400.0},
            {"coenti": 99999, "damesano": 202512, "cmpid": 518, "valor": 999.0},
        ]
    )


def _derive(table: pd.DataFrame, *, company: str = "12345", year: int = 2025):
    return derive_susep_profitability_metrics(
        table, susep_company_code=company, fiscal_year=year
    )


def test_profitability_uses_december_ytd_and_average_balances() -> None:
    metrics = _derive(_table())
    assert metrics.net_income == pytest.approx(20.0)
    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa == pytest.approx(0.04)
    assert metrics.point_in_time_eligible is False
    assert insurance_profitability_features(
        _table(), susep_company_code="12345", fiscal_year=2025
    ) == {"roe": pytest.approx(0.20), "roa": pytest.approx(0.04)}


def test_profitability_allows_negative_net_income() -> None:
    metrics = _derive(_table(net_income=-10.0))
    assert metrics.roe == pytest.approx(-0.10)
    assert metrics.roa == pytest.approx(-0.02)


def test_duplicate_net_income_fails_roe_and_roa_closed() -> None:
    duplicate = pd.DataFrame(
        [{"coenti": 12345, "damesano": 202512, "cmpid": 518, "valor": 20.0}]
    )
    metrics = _derive(pd.concat([_table(), duplicate], ignore_index=True))
    assert metrics.net_income is None
    assert metrics.roe is None
    assert metrics.roa is None


def test_missing_prior_equity_only_blocks_roe() -> None:
    table = _table()
    table = table.loc[
        ~((table["damesano"] == 202412) & (table["cmpid"] == 3333))
    ].copy()
    metrics = _derive(table)
    assert metrics.roe is None
    assert metrics.roa == pytest.approx(0.04)


def test_missing_prior_assets_only_blocks_roa() -> None:
    table = _table()
    table = table.loc[
        ~((table["damesano"] == 202412) & (table["cmpid"] == 1039))
    ].copy()
    metrics = _derive(table)
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
    metrics = _derive(table)
    assert metrics.roe is None
    assert metrics.roa == pytest.approx(0.04)


def test_nonnumeric_value_fails_only_dependent_metric() -> None:
    table = _table().astype({"valor": "object"})
    table.loc[
        (table["damesano"] == 202512) & (table["cmpid"] == 1039), "valor"
    ] = "UNKNOWN"
    metrics = _derive(table)
    assert metrics.roe == pytest.approx(0.20)
    assert metrics.roa is None


def test_wrong_company_and_pre_contract_year_are_unknown() -> None:
    wrong_company = _derive(_table(), company="54321")
    old_year = _derive(_table(), year=2013)
    assert wrong_company.roe is None
    assert wrong_company.roa is None
    assert old_year.roe is None
    assert old_year.roa is None


def test_company_code_must_be_numeric() -> None:
    with pytest.raises(ValueError, match="only digits"):
        _derive(_table(), company="ABC")


def test_required_schema_is_enforced() -> None:
    with pytest.raises(ValueError, match="cmpid"):
        _derive(pd.DataFrame([{"coenti": 12345, "damesano": 202512, "valor": 1.0}]))
