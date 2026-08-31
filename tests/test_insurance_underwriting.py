import math

import pandas as pd
import pytest

from ultimate_stock_analyzer.scoring.insurance_underwriting import (
    derive_susep_loss_ratio,
    derive_susep_underwriting_metrics,
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
                    "desp_com": 20.0,
                }
            )
    return pd.DataFrame(rows)


def _accounting_rows(*, code: int = 12345, admin: float = -240.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"coenti": code, "damesano": 202512, "cmpid": 4069, "valor": admin, "quadro": 23},
            {"coenti": code, "damesano": 202511, "cmpid": 4069, "valor": -220.0, "quadro": 23},
            {"coenti": code, "damesano": 202512, "cmpid": 518, "valor": 100.0, "quadro": 23},
            {"coenti": 99999, "damesano": 202512, "cmpid": 4069, "valor": -999.0, "quadro": 23},
        ]
    )


def test_underwriting_promotes_verified_expense_and_combined_ratios() -> None:
    table = pd.concat([_full_year_rows(), _full_year_rows(code=99999)], ignore_index=True)

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.complete_months is True
    assert metrics.annual_earned_premiums == pytest.approx(2400.0)
    assert metrics.annual_incurred_claims == pytest.approx(1440.0)
    assert metrics.annual_commercial_expenses == pytest.approx(480.0)
    assert metrics.annual_administrative_expenses == pytest.approx(240.0)
    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.commercial_expense_ratio == pytest.approx(0.20)
    assert metrics.administrative_expense_ratio == pytest.approx(0.10)
    assert metrics.expense_ratio == pytest.approx(0.30)
    assert metrics.combined_ratio == pytest.approx(0.90)
    assert metrics.point_in_time_eligible is False
    assert metrics.source == "SUSEP_SES_DERIVED"

    assert insurance_underwriting_features(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    ) == {
        "combined_ratio": pytest.approx(0.90),
        "loss_ratio": pytest.approx(0.60),
        "expense_ratio": pytest.approx(0.30),
    }


def test_admin_expense_uses_only_december_ytd_cmpid_4069() -> None:
    accounting = _accounting_rows()
    metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=accounting,
    )

    # November is deliberately -220. If monthly DRE values were incorrectly summed,
    # administrative expense would be 460 instead of the December YTD value of 240.
    assert metrics.annual_administrative_expenses == pytest.approx(240.0)
    assert metrics.administrative_expense_ratio == pytest.approx(0.10)


def test_backward_compatible_loss_ratio_entry_point_preserves_existing_evidence() -> None:
    metrics = derive_susep_loss_ratio(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
    )
    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.commercial_expense_ratio == pytest.approx(0.20)
    assert metrics.administrative_expense_ratio is None
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None


def test_underwriting_requires_all_twelve_operating_months() -> None:
    table = _full_year_rows()
    table = table[table["damesano"] != 202507]

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.complete_months is False
    assert metrics.annual_earned_premiums is None
    assert metrics.loss_ratio is None
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None


def test_invalid_claims_disable_loss_and_combined_but_preserve_expense_ratio() -> None:
    table = _full_year_rows()
    table["sinistro_ocorrido"] = table["sinistro_ocorrido"].astype(object)
    table.loc[0, "sinistro_ocorrido"] = "invalid"

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.loss_ratio is None
    assert metrics.annual_incurred_claims is None
    assert metrics.expense_ratio == pytest.approx(0.30)
    assert metrics.combined_ratio is None


def test_invalid_commercial_expense_preserves_loss_but_disables_total_expense_metrics() -> None:
    table = _full_year_rows()
    table["desp_com"] = table["desp_com"].astype(object)
    table.loc[0, "desp_com"] = "invalid"

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.commercial_expense_ratio is None
    assert metrics.administrative_expense_ratio == pytest.approx(0.10)
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None


def test_missing_admin_evidence_preserves_existing_metrics() -> None:
    metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=None,
    )

    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.commercial_expense_ratio == pytest.approx(0.20)
    assert metrics.administrative_expense_ratio is None
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None


def test_missing_claims_column_allows_expense_ratio_but_not_combined() -> None:
    table = _full_year_rows().drop(columns=["sinistro_ocorrido"])
    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.loss_ratio is None
    assert metrics.expense_ratio == pytest.approx(0.30)
    assert metrics.combined_ratio is None


def test_missing_commercial_column_preserves_loss_ratio() -> None:
    table = _full_year_rows().drop(columns=["desp_com"])
    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    )

    assert metrics.loss_ratio == pytest.approx(0.60)
    assert metrics.administrative_expense_ratio == pytest.approx(0.10)
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None


def test_admin_expense_sign_is_fail_closed_not_absolute_value() -> None:
    positive_source = _accounting_rows(admin=240.0)
    metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=positive_source,
    )

    assert metrics.annual_administrative_expenses is None
    assert metrics.administrative_expense_ratio is None
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None

    zero_source = _accounting_rows(admin=0.0)
    zero_metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=zero_source,
    )
    assert zero_metrics.annual_administrative_expenses == pytest.approx(0.0)
    assert zero_metrics.expense_ratio == pytest.approx(0.20)


def test_duplicate_or_invalid_december_admin_fails_only_dependent_metrics() -> None:
    duplicate = pd.concat([_accounting_rows(), _accounting_rows().iloc[[0]]], ignore_index=True)
    duplicate_metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=duplicate,
    )
    assert duplicate_metrics.loss_ratio == pytest.approx(0.60)
    assert duplicate_metrics.expense_ratio is None
    assert duplicate_metrics.combined_ratio is None

    invalid = _accounting_rows().astype({"valor": "object"})
    invalid.loc[invalid["cmpid"] == 4069, "valor"] = "invalid"
    invalid_metrics = derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=invalid,
    )
    assert invalid_metrics.loss_ratio == pytest.approx(0.60)
    assert invalid_metrics.expense_ratio is None


def test_nonfinite_admin_and_negative_operating_numerators_fail_closed() -> None:
    nonfinite = _accounting_rows(admin=-math.inf)
    assert derive_susep_underwriting_metrics(
        _full_year_rows(),
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=nonfinite,
    ).expense_ratio is None

    negative_claims = _full_year_rows()
    negative_claims["sinistro_ocorrido"] = -1.0
    negative_commercial = _full_year_rows()
    negative_commercial["desp_com"] = -1.0

    assert derive_susep_underwriting_metrics(
        negative_claims,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    ).combined_ratio is None
    assert derive_susep_underwriting_metrics(
        negative_commercial,
        susep_company_code="12345",
        fiscal_year=2025,
        accounting_table=_accounting_rows(),
    ).expense_ratio is None


def test_pre_current_susep_definition_year_keeps_all_ratios_unknown() -> None:
    table = _full_year_rows()
    table["damesano"] = table["damesano"] - 1200

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code="12345",
        fiscal_year=2013,
        accounting_table=_accounting_rows(),
    )

    assert metrics.loss_ratio is None
    assert metrics.expense_ratio is None
    assert metrics.combined_ratio is None
    assert metrics.complete_months is False


def test_underwriting_requires_common_columns_and_numeric_company_code() -> None:
    table = _full_year_rows().drop(columns=["premio_ganho"])

    with pytest.raises(ValueError, match="premio_ganho"):
        derive_susep_underwriting_metrics(
            table,
            susep_company_code="12345",
            fiscal_year=2025,
        )
    with pytest.raises(ValueError, match="only digits"):
        derive_susep_underwriting_metrics(
            _full_year_rows(),
            susep_company_code="PSSA3",
            fiscal_year=2025,
        )
