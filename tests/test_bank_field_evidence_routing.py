from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bank_field_evidence_routing import (
    BANK_FIELD_EVIDENCE_MISSING,
    BANK_FIELD_NOT_YET_AVAILABLE_AS_OF,
    route_bank_field_evidence,
)
from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_canonical_mapping_audit import (
    CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN,
    CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_numeric_values import (
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    Pillar3PrudentialObservation,
)
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    FinancialStatementLine,
)


COLLECTED_AT = datetime(2026, 9, 3, tzinfo=UTC)
PROFILE_AVAILABLE_FROM = datetime(2025, 4, 1, tzinfo=UTC)
CVM_AVAILABLE_FROM = datetime(2025, 2, 28, tzinfo=UTC)


def _profile(
    *,
    point_in_time_eligible: bool = False,
    annual_net_income: float | None = 42.0,
    basel_ratio: float | None = 0.16,
    tier1_ratio: float | None = 0.14,
    core_equity_tier1_ratio: float | None = 0.12,
    leverage_ratio: float | None = 0.07,
) -> BankPrudentialAnnualRecord:
    return BankPrudentialAnnualRecord(
        company_id="cvm:19348",
        cvm_code=19348,
        cnpj="60.872.504/0001-23",
        cnpj_root="60872504",
        fiscal_year=2024,
        reference_date=date(2024, 12, 31),
        ifdata_cod_inst="C0080099",
        ifdata_name="ITAU - PRUDENCIAL",
        total_assets=2_400.0,
        prior_total_assets=2_000.0,
        equity=240.0,
        prior_equity=200.0,
        gross_credit_portfolio=1_100.0,
        prior_gross_credit_portfolio=900.0,
        annual_net_income=annual_net_income,
        annual_credit_loss_result=-20.0,
        basel_ratio=basel_ratio,
        tier1_ratio=tier1_ratio,
        core_equity_tier1_ratio=core_equity_tier1_ratio,
        leverage_ratio=leverage_ratio,
        available_from_estimate=PROFILE_AVAILABLE_FROM,
        collected_at=COLLECTED_AT,
        point_in_time_eligible=point_in_time_eligible,
    )


def _cvm_line(
    account_code: str,
    account_name: str,
    value: float,
    *,
    available_from: datetime = CVM_AVAILABLE_FROM,
    version: int = 1,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id="cvm:19348",
        cvm_code=19348,
        cnpj="60.872.504/0001-23",
        company_name="ITAÚ UNIBANCO HOLDING S.A.",
        document_type="DFP",
        statement="DRE",
        consolidation_scope="DF Consolidado",
        reference_date=date(2024, 12, 31),
        fiscal_order="ÚLTIMO",
        account_code=account_code,
        account_name=account_name,
        value_brl=value,
        version=version,
        available_from=available_from,
        collected_at=COLLECTED_AT,
        source_document="dfp_cia_aberta_DRE_con_2024.csv",
    )


def _cvm_net_income_lines(
    *,
    available_from: datetime = CVM_AVAILABLE_FROM,
) -> list[FinancialStatementLine]:
    return [
        _cvm_line(
            "3.07",
            "Resultado Antes dos Tributos sobre o Lucro",
            50.0,
            available_from=available_from,
        ),
        _cvm_line(
            "3.08",
            "Imposto de Renda e Contribuição Social sobre o Lucro",
            -8.0,
            available_from=available_from,
        ),
        _cvm_line(
            "3.09",
            "Lucro/Prejuízo Consolidado do Período",
            42.0,
            available_from=available_from,
        ),
    ]


def _pillar3() -> Pillar3PrudentialObservation:
    return Pillar3PrudentialObservation(
        prudential_reference_date=date(2024, 12, 31),
        available_from=datetime(2025, 3, 31, tzinfo=UTC),
        delivery_protocol="ipe:123",
        version=1,
        source_url="https://example.com/pillar3.pdf",
        pdf_sha256="a" * 64,
        core_equity_tier1_ratio=0.137,
        tier1_ratio=0.150,
        basel_ratio=0.165,
        leverage_ratio=0.071,
    )


def test_ifdata_values_are_visible_but_not_strict_pit() -> None:
    report = route_bank_field_evidence(
        _profile(),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
    )

    annual = report.decision_for("annual_net_income")
    assert annual.status == "PRESENT_NOT_POINT_IN_TIME"
    assert annual.source == "BCB_IFDATA"
    assert annual.contract_admissible is False
    assert annual.point_in_time_eligible is False
    assert report.observed_critical_coverage == pytest.approx(1.0)
    assert report.contract_scope_compatible_critical_coverage == pytest.approx(1.0)
    assert report.strict_point_in_time_critical_coverage == pytest.approx(0.0)
    assert report.bank_evidence_point_in_time_ready is False
    assert report.readiness_promotion_allowed is False


def test_cvm_309_routes_as_official_scope_mismatch_when_ifdata_is_missing() -> None:
    report = route_bank_field_evidence(
        _profile(annual_net_income=None),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
        cvm_lines=_cvm_net_income_lines(),
    )

    annual = report.decision_for("annual_net_income")
    assert annual.status == "OFFICIAL_SCOPE_MISMATCH"
    assert annual.source == "CVM_DFP"
    assert annual.source_scope == "ISSUER_CONSOLIDATED"
    assert annual.value == pytest.approx(42.0)
    assert annual.contract_admissible is False
    assert CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN in annual.blockers
    assert CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN in annual.blockers
    assert report.observed_critical_coverage == pytest.approx(1.0)
    assert report.contract_scope_compatible_critical_coverage == pytest.approx(0.9)
    assert report.strict_point_in_time_critical_coverage == pytest.approx(0.0)


def test_cvm_309_is_kept_as_alternative_when_ifdata_value_exists() -> None:
    report = route_bank_field_evidence(
        _profile(annual_net_income=44.0),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
        cvm_lines=_cvm_net_income_lines(),
    )

    annual = report.decision_for("annual_net_income")
    assert annual.status == "PRESENT_NOT_POINT_IN_TIME"
    assert annual.source == "BCB_IFDATA"
    assert [item.source for item in annual.alternatives] == ["CVM_DFP"]
    assert annual.alternatives[0].contract_scope_compatible is False


def test_as_of_excludes_future_cvm_filing() -> None:
    future = datetime(2025, 8, 1, tzinfo=UTC)
    report = route_bank_field_evidence(
        _profile(annual_net_income=None),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
        cvm_lines=_cvm_net_income_lines(available_from=future),
    )

    annual = report.decision_for("annual_net_income")
    assert annual.status == "MISSING"
    assert annual.selected is None
    assert BANK_FIELD_EVIDENCE_MISSING in annual.blockers


def test_as_of_excludes_future_ifdata_estimate() -> None:
    report = route_bank_field_evidence(
        _profile(),
        as_of=datetime(2025, 3, 1, tzinfo=UTC),
    )

    assets = report.decision_for("total_assets")
    assert assets.status == "MISSING"
    assert assets.selected is None
    assert BANK_FIELD_NOT_YET_AVAILABLE_AS_OF in assets.blockers


def test_pillar3_routes_prudential_ratios_without_readiness_promotion() -> None:
    report = route_bank_field_evidence(
        _profile(
            basel_ratio=None,
            tier1_ratio=None,
            core_equity_tier1_ratio=None,
            leverage_ratio=None,
        ),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
        pillar3_observations=(_pillar3(),),
    )

    basel = report.decision_for("basel_ratio")
    assert basel.status == "PRESENT_NOT_POINT_IN_TIME"
    assert basel.source == "CVM_IPE_PILLAR3"
    assert basel.source_scope == "PRUDENTIAL_CONGLOMERATE"
    assert basel.selected is not None
    assert basel.selected.contract_scope_compatible is True
    assert basel.point_in_time_eligible is False
    assert PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN in basel.blockers
    assert report.bank_evidence_point_in_time_ready is False
    assert report.readiness_promotion_allowed is False


def test_record_level_pit_profile_can_make_critical_fields_admissible() -> None:
    report = route_bank_field_evidence(
        _profile(point_in_time_eligible=True),
        as_of=datetime(2025, 6, 30, tzinfo=UTC),
    )

    assert all(
        report.decision_for(field).status == "POINT_IN_TIME_ADMISSIBLE"
        for field in (
            "total_assets",
            "prior_total_assets",
            "equity",
            "prior_equity",
            "gross_credit_portfolio",
            "prior_gross_credit_portfolio",
            "annual_net_income",
            "annual_credit_loss_result",
            "basel_ratio",
            "tier1_ratio",
        )
    )
    assert report.strict_point_in_time_critical_coverage == pytest.approx(1.0)
    assert report.bank_evidence_point_in_time_ready is True
    assert report.readiness_promotion_allowed is False
