import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_growth import (
    derive_susep_premiums_cagr_5y,
    insurance_growth_features,
)


def _history(*, code: int = 12345, end_year: int = 2025) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for year in range(end_year - 5, end_year + 1):
        annual_scale = 1.1 ** (year - (end_year - 5))
        for month in range(1, 13):
            for branch in (1, 2):
                rows.append(
                    {
                        "damesano": year * 100 + month,
                        "coenti": code,
                        "coramo": branch,
                        "premio_ganho": 100.0 * annual_scale,
                    }
                )
    return pd.DataFrame(rows)


def test_premiums_cagr_requires_six_exact_consecutive_full_years() -> None:
    table = pd.concat([_history(), _history(code=99999)], ignore_index=True)

    metrics = derive_susep_premiums_cagr_5y(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    )

    assert metrics.complete_history is True
    assert metrics.start_year == 2020
    assert metrics.premiums_cagr_5y == pytest.approx(0.10)
    assert metrics.point_in_time_eligible is False
    assert insurance_growth_features(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    ) == {"premiums_cagr_5y": pytest.approx(0.10)}


def test_premiums_cagr_fails_closed_when_one_month_is_missing() -> None:
    table = _history()
    table = table[table["damesano"] != 202207]

    metrics = derive_susep_premiums_cagr_5y(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    )

    assert metrics.complete_history is False
    assert metrics.premiums_cagr_5y is None


def test_premiums_cagr_fails_closed_on_non_numeric_or_non_positive_evidence() -> None:
    invalid = _history()
    invalid["premio_ganho"] = invalid["premio_ganho"].astype(object)
    invalid.loc[0, "premio_ganho"] = "invalid"
    zero_start = _history()
    zero_start.loc[zero_start["damesano"] // 100 == 2020, "premio_ganho"] = 0.0

    assert derive_susep_premiums_cagr_5y(
        invalid,
        susep_company_code="12345",
        fiscal_year=2025,
    ).premiums_cagr_5y is None
    assert derive_susep_premiums_cagr_5y(
        zero_start,
        susep_company_code="12345",
        fiscal_year=2025,
    ).premiums_cagr_5y is None


def test_premiums_cagr_does_not_mix_pre_current_susep_definition_years() -> None:
    table = _history(end_year=2018)

    metrics = derive_susep_premiums_cagr_5y(
        table,
        susep_company_code="12345",
        fiscal_year=2018,
    )

    assert metrics.complete_history is False
    assert metrics.premiums_cagr_5y is None


def test_premiums_cagr_requires_exact_columns_and_numeric_company_code() -> None:
    with pytest.raises(ValueError, match="premio_ganho"):
        derive_susep_premiums_cagr_5y(
            _history().drop(columns=["premio_ganho"]),
            susep_company_code="12345",
            fiscal_year=2025,
        )
    with pytest.raises(ValueError, match="only digits"):
        derive_susep_premiums_cagr_5y(
            _history(),
            susep_company_code="PSSA3",
            fiscal_year=2025,
        )
