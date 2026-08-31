import math

import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_net_income_growth import (
    derive_susep_net_income_cagr_5y,
    insurance_net_income_growth_features,
)


def _table(values: dict[int, float], *, code: int = 6947) -> pd.DataFrame:
    rows = [
        {"coenti": code, "damesano": year * 100 + 12, "cmpid": 518, "valor": value}
        for year, value in values.items()
    ]
    return pd.DataFrame(rows)


def test_net_income_cagr_requires_six_consecutive_december_values() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 121.0, 2022: 133.1, 2023: 146.41, 2024: 161.051})

    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="06947", fiscal_year=2024
    )

    assert metrics.complete_history is True
    assert metrics.start_year == 2019
    assert metrics.start_net_income == 100.0
    assert metrics.end_net_income == pytest.approx(161.051)
    assert metrics.net_income_cagr_5y == pytest.approx(0.1)
    assert metrics.point_in_time_eligible is False


def test_growth_feature_maps_only_verified_metric() -> None:
    table = _table({2019: 100.0, 2020: 100.0, 2021: 100.0, 2022: 100.0, 2023: 100.0, 2024: 200.0})
    features = insurance_net_income_growth_features(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert set(features) == {"net_income_cagr_5y"}
    assert features["net_income_cagr_5y"] == pytest.approx(2 ** (1 / 5) - 1)


def test_missing_intermediate_year_fails_closed() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 120.0, 2023: 140.0, 2024: 150.0})
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_duplicate_december_value_fails_closed() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: 130.0, 2023: 140.0, 2024: 150.0})
    table = pd.concat(
        [table, pd.DataFrame([{"coenti": 6947, "damesano": 202212, "cmpid": 518, "valor": 130.0}])],
        ignore_index=True,
    )
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_non_numeric_value_fails_closed() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: 130.0, 2023: 140.0, 2024: 150.0})
    table.loc[table["damesano"] == 202212, "valor"] = "invalid"
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_negative_intermediate_profit_is_valid_history_when_endpoints_positive() -> None:
    table = _table({2019: 100.0, 2020: -10.0, 2021: 20.0, 2022: 30.0, 2023: 40.0, 2024: 200.0})
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is True
    assert metrics.net_income_cagr_5y == pytest.approx(2 ** (1 / 5) - 1)


@pytest.mark.parametrize("start,end", [(0.0, 100.0), (-10.0, 100.0), (100.0, 0.0), (100.0, -10.0)])
def test_nonpositive_endpoint_keeps_history_but_cagr_unknown(start: float, end: float) -> None:
    table = _table({2019: start, 2020: 10.0, 2021: 20.0, 2022: 30.0, 2023: 40.0, 2024: end})
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is True
    assert metrics.start_net_income == start
    assert metrics.end_net_income == end
    assert metrics.net_income_cagr_5y is None


def test_pre_current_accounting_era_fails_closed() -> None:
    table = _table({2008: 10.0, 2009: 20.0, 2010: 30.0, 2011: 40.0, 2012: 50.0, 2013: 60.0})
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2013
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_wrong_company_and_wrong_cmpid_do_not_count() -> None:
    rows = []
    for year in range(2019, 2025):
        rows.append({"coenti": 9999, "damesano": year * 100 + 12, "cmpid": 518, "valor": 100.0})
        rows.append({"coenti": 6947, "damesano": year * 100 + 12, "cmpid": 999, "valor": 100.0})
    metrics = derive_susep_net_income_cagr_5y(
        pd.DataFrame(rows), susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_infinite_value_fails_closed() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: math.inf, 2023: 140.0, 2024: 150.0})
    metrics = derive_susep_net_income_cagr_5y(
        table, susep_company_code="6947", fiscal_year=2024
    )
    assert metrics.complete_history is False
    assert metrics.net_income_cagr_5y is None


def test_invalid_company_code_and_schema_fail_closed() -> None:
    table = _table({2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: 130.0, 2023: 140.0, 2024: 150.0})
    with pytest.raises(ValueError, match="only digits"):
        derive_susep_net_income_cagr_5y(table, susep_company_code="ABC", fiscal_year=2024)
    with pytest.raises(ValueError, match="missing required"):
        derive_susep_net_income_cagr_5y(table.drop(columns=["cmpid"]), susep_company_code="6947", fiscal_year=2024)
