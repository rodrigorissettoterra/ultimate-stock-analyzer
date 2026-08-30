from datetime import UTC, date, datetime

from ultimate_stock_analyzer.collectors.susep_ses import (
    SUSEP_SES_DOWNLOAD_URL,
    source_contract,
)
from ultimate_stock_analyzer.domain.master import InsuranceSusepAnnualRecord


def test_susep_source_contract_is_official_fail_closed_and_non_pit() -> None:
    contract = source_contract()

    assert contract.source == "SUSEP_SES"
    assert contract.source_kind == "OFFICIAL_PUBLIC"
    assert contract.update_cadence == "WEEKLY"
    assert contract.revision_aware is False
    assert contract.point_in_time_eligible is False
    assert contract.licensed_entity_registry_required is True
    assert contract.fuzzy_identity_matching_allowed is False
    assert contract.download_url == SUSEP_SES_DOWNLOAD_URL


def test_insurance_record_keeps_unverified_scoring_metrics_unknown() -> None:
    record = InsuranceSusepAnnualRecord(
        company_id="cvm:00000",
        cvm_code=0,
        cnpj="00.000.000/0001-00",
        fiscal_year=2025,
        reference_date=date(2025, 12, 31),
        susep_company_code="00000",
        susep_name="SEGURADORA DE TESTE S.A.",
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert record.roe is None
    assert record.roa is None
    assert record.combined_ratio is None
    assert record.loss_ratio is None
    assert record.expense_ratio is None
    assert record.solvency_ratio is None
    assert record.capital_adequacy_ratio is None
    assert record.technical_provisions_coverage is None
    assert record.point_in_time_eligible is False
    assert record.source == "SUSEP_SES"
