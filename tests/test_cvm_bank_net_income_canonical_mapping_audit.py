from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_canonical_mapping_audit import (
    CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN,
    CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    CVM_BANK_NET_INCOME_ACCOUNT_309_LABEL_MISMATCH,
    CVM_BANK_NET_INCOME_AVAILABILITY_MISSING,
    CVM_BANK_NET_INCOME_DUPLICATE_ACCOUNT_CODE,
    CVM_BANK_NET_INCOME_MAPPING_WINDOW_INCOMPLETE,
    audit_cvm_bank_net_income_canonical_mapping,
)
from ultimate_stock_analyzer.domain.master import FinancialStatementLine


def _line(
    *,
    year: int,
    version: int,
    code: str,
    name: str,
    value: float,
    available: bool = True,
) -> FinancialStatementLine:
    available_from = (
        datetime(year + 1, 2, 5, tzinfo=UTC) if available else None
    )
    return FinancialStatementLine(
        company_id="cvm:19348",
        cvm_code=19348,
        company_name="ITAU UNIBANCO HOLDING S.A.",
        document_type="DFP",
        statement="DRE",
        consolidation_scope="DF Consolidado - Demonstração do Resultado",
        reference_date=date(year, 12, 31),
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        fiscal_order="ÚLTIMO",
        account_code=code,
        account_name=name,
        value_brl=value,
        version=version,
        received_at=available_from,
        available_from=available_from,
        collected_at=datetime(year + 1, 4, 1, tzinfo=UTC),
        source_document=f"dfp_cia_aberta_DRE_con_{year}.csv",
    )


def _version_lines(year: int, version: int = 1) -> list[FinancialStatementLine]:
    return [
        _line(
            year=year,
            version=version,
            code="3.07",
            name="Resultado Líquido das Operações Continuadas",
            value=100.0,
        ),
        _line(
            year=year,
            version=version,
            code="3.08",
            name="Resultado Líquido das Operações Descontinuadas",
            value=0.0,
        ),
        _line(
            year=year,
            version=version,
            code="3.09",
            name="Lucro/Prejuízo Consolidado do Período",
            value=100.0,
        ),
        _line(
            year=year,
            version=version,
            code="3.09.01",
            name="Atribuído a Sócios da Empresa Controladora",
            value=90.0,
        ),
        _line(
            year=year,
            version=version,
            code="3.09.02",
            name="Atribuído a Sócios Não Controladores",
            value=10.0,
        ),
    ]


def test_validates_309_across_years_and_observed_versions() -> None:
    lines = _version_lines(2024, 1) + _version_lines(2025, 1)
    lines += _version_lines(2025, 2)

    audit = audit_cvm_bank_net_income_canonical_mapping(
        lines,
        cvm_code=19348,
        years=(2024, 2025),
    )

    assert audit.observed_years == (2024, 2025)
    assert [(item.fiscal_year, item.version) for item in audit.versions] == [
        (2024, 1),
        (2025, 1),
        (2025, 2),
    ]
    assert all(item.observed_mapping_validated for item in audit.versions)
    assert all(item.attribution_identity_validated for item in audit.versions)
    assert audit.canonical_mapping_supported_for_observed_scope is True
    assert audit.canonical_account_code == "3.09"
    assert audit.revision_history_completeness_proven is False
    assert audit.prudential_scope_alignment_proven is False
    assert CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN in audit.blockers
    assert CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN in audit.blockers
    assert audit.bank_evidence_point_in_time_ready is False
    assert audit.readiness_promotion_allowed is False


def test_label_mismatch_prevents_canonical_mapping() -> None:
    lines = _version_lines(2024)
    lines = [
        _line(
            year=2024,
            version=1,
            code=item.account_code,
            name=("Resultado Final" if item.account_code == "3.09" else item.account_name),
            value=item.value_brl,
        )
        for item in lines
    ]

    audit = audit_cvm_bank_net_income_canonical_mapping(
        lines,
        cvm_code=19348,
        years=(2024,),
    )

    validation = audit.versions[0]
    assert validation.observed_mapping_validated is False
    assert CVM_BANK_NET_INCOME_ACCOUNT_309_LABEL_MISMATCH in validation.blockers
    assert audit.canonical_account_code is None


def test_missing_year_keeps_mapping_window_incomplete() -> None:
    audit = audit_cvm_bank_net_income_canonical_mapping(
        _version_lines(2025),
        cvm_code=19348,
        years=(2024, 2025),
    )

    assert audit.observed_years == (2025,)
    assert audit.canonical_mapping_supported_for_observed_scope is False
    assert CVM_BANK_NET_INCOME_MAPPING_WINDOW_INCOMPLETE in audit.blockers


def test_missing_309_availability_fails_version() -> None:
    lines = _version_lines(2024)
    replacement = _line(
        year=2024,
        version=1,
        code="3.09",
        name="Lucro/Prejuízo Consolidado do Período",
        value=100.0,
        available=False,
    )
    lines = [replacement if item.account_code == "3.09" else item for item in lines]

    audit = audit_cvm_bank_net_income_canonical_mapping(
        lines,
        cvm_code=19348,
        years=(2024,),
    )

    assert audit.versions[0].availability_timestamp_validated is False
    assert CVM_BANK_NET_INCOME_AVAILABILITY_MISSING in audit.versions[0].blockers
    assert audit.canonical_mapping_supported_for_observed_scope is False


def test_duplicate_account_code_is_fail_closed() -> None:
    lines = _version_lines(2024)
    lines.append(
        _line(
            year=2024,
            version=1,
            code="3.09",
            name="Lucro/Prejuízo Consolidado do Período",
            value=100.0,
        )
    )

    audit = audit_cvm_bank_net_income_canonical_mapping(
        lines,
        cvm_code=19348,
        years=(2024,),
    )

    validation = audit.versions[0]
    assert validation.duplicate_account_codes == ("3.09",)
    assert CVM_BANK_NET_INCOME_DUPLICATE_ACCOUNT_CODE in validation.blockers
    assert validation.observed_mapping_validated is False
