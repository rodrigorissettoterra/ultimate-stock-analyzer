import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_capital import (
    derive_susep_solvency_ratio,
    insurance_capital_features,
)


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"coenti": 12345, "damesano": 202512, "plajustado": 150.0, "CMR": 100.0},
            {"coenti": 12345, "damesano": 202511, "plajustado": 140.0, "CMR": 100.0},
            {"coenti": 99999, "damesano": 202512, "plajustado": 400.0, "CMR": 100.0},
        ]
    )


def test_solvency_ratio_uses_exact_year_end_company_snapshot() -> None:
    metrics = derive_susep_solvency_ratio(
        _rows(), susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.reference_period == 202512
    assert metrics.adjusted_equity == pytest.approx(150.0)
    assert metrics.capital_minimum_required == pytest.approx(100.0)
    assert metrics.capital_surplus == pytest.approx(50.0)
    assert metrics.solvency_ratio == pytest.approx(1.5)
    assert metrics.point_in_time_eligible is False
    assert insurance_capital_features(
        _rows(), susep_company_code="12345", fiscal_year=2025
    ) == {"solvency_ratio": pytest.approx(1.5)}


def test_solvency_ratio_preserves_regulatory_insufficiency_below_one() -> None:
    table = _rows()
    table.loc[0, "plajustado"] = 80.0

    metrics = derive_susep_solvency_ratio(
        table, susep_company_code="12345", fiscal_year=2025
    )

    assert metrics.capital_surplus == pytest.approx(-20.0)
    assert metrics.solvency_ratio == pytest.approx(0.8)


def test_solvency_ratio_fails_closed_on_missing_duplicate_or_invalid_evidence() -> None:
    missing = _rows()[lambda frame: frame["damesano"] != 202512]
    assert derive_susep_solvency_ratio(
        missing, susep_company_code="12345", fiscal_year=2025
    ).solvency_ratio is None

    duplicate = pd.concat([_rows(), _rows().iloc[[0]]], ignore_index=True)
    assert derive_susep_solvency_ratio(
        duplicate, susep_company_code="12345", fiscal_year=2025
    ).solvency_ratio is None

    zero_cmr = _rows()
    zero_cmr.loc[0, "CMR"] = 0.0
    assert derive_susep_solvency_ratio(
        zero_cmr, susep_company_code="12345", fiscal_year=2025
    ).solvency_ratio is None


def test_solvency_ratio_requires_exact_schema_and_official_numeric_identity() -> None:
    with pytest.raises(ValueError, match="CMR"):
        derive_susep_solvency_ratio(
            _rows().drop(columns=["CMR"]),
            susep_company_code="12345",
            fiscal_year=2025,
        )

    with pytest.raises(ValueError, match="only digits"):
        derive_susep_solvency_ratio(
            _rows(), susep_company_code="PSSA3", fiscal_year=2025
        )
