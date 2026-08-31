import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_underwriting import (
    derive_susep_loss_ratio,
    insurance_underwriting_features,
)


def _full_year_rows(*, code: int = 12345) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for month in range(1, 13):
        for branch in (1, 2):
            rows.append(
                {
                    "damesano": 202500 + month,
                    "coenti": code,
                    "cogrupo": 1,
                    "coramo": branch,
                    "premio_ganho": 100.0,
                    "sinistro_ocorrido": 60.0,
                }
            )
    return pd.DataFrame(rows)


def test_loss_ratio_aggregates_exact_company_full_year() -> None:
    table = _full_year_rows()
    other = _full_year_rows(code=99999)
    table = pd.concat([table, other], ignore_index=True)

    metrics = derive_susep_loss_ratio(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    )

    assert metrics.complete_months is True
    assert metrics.annual_earned_premiums == pytest.approx(2400.0)
    assert metrics.annual_incurred_claims == pytest.approx(1440.0)
    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.point_in_time_eligible is False
    assert metrics.source == "SUSEP_SES_DERIVED"
    assert insurance_underwriting_features(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    ) == {"loss_ratio": pytest.approx(0.60)}


def test_loss_ratio_requires_all_twelve_months() -> None:
    table = _full_year_rows()
    table = table[table["damesano"] != 202507]

    metrics = derive_susep_loss_ratio(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    )

    assert metrics.complete_months is False
    assert metrics.annual_earned_premiums is None
    assert metrics.annual_incurred_claims is None
    assert metrics.loss_ratio is None


def test_loss_ratio_fails_closed_on_non_numeric_source_value() -> None:
    table = _full_year_rows()
    table["sinistro_ocorrido"] = table["sinistro_ocorrido"].astype(object)
    table.loc[0, "sinistro_ocorrido"] = "invalid"

    metrics = derive_susep_loss_ratio(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
    )

    assert metrics.complete_months is True
    assert metrics.loss_ratio is None


def test_loss_ratio_fails_closed_on_non_positive_denominator_or_negative_claims() -> None:
    zero_premium = _full_year_rows()
    zero_premium["premio_ganho"] = 0.0
    negative_claims = _full_year_rows()
    negative_claims["sinistro_ocorrido"] = -1.0

    assert (
        derive_susep_loss_ratio(
            zero_premium,
            susep_company_code="12345",
            fiscal_year=2025,
        ).loss_ratio
        is None
    )
    assert (
        derive_susep_loss_ratio(
            negative_claims,
            susep_company_code="12345",
            fiscal_year=2025,
        ).loss_ratio
        is None
    )


def test_loss_ratio_does_not_mix_pre_current_susep_definition_years() -> None:
    table = _full_year_rows()
    table["damesano"] = table["damesano"] - 1200

    metrics = derive_susep_loss_ratio(
        table,
        susep_company_code="12345",
        fiscal_year=2013,
    )

    assert metrics.loss_ratio is None
    assert metrics.complete_months is False


def test_loss_ratio_requires_exact_official_columns_and_numeric_company_code() -> None:
    table = _full_year_rows().drop(columns=["sinistro_ocorrido"])

    with pytest.raises(ValueError, match="sinistro_ocorrido"):
        derive_susep_loss_ratio(
            table,
            susep_company_code="12345",
            fiscal_year=2025,
        )
    with pytest.raises(ValueError, match="only digits"):
        derive_susep_loss_ratio(
            _full_year_rows(),
            susep_company_code="PSSA3",
            fiscal_year=2025,
        )
