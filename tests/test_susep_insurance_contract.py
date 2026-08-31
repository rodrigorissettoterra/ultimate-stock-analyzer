from datetime import UTC, date, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from ultimate_stock_analyzer.collectors.susep_ses import (
    CANDIDATE_SOURCE_TABLES,
    SUSEP_SES_DOWNLOAD_URL,
    SusepSesCollector,
    source_contract,
)
from ultimate_stock_analyzer.domain.master import InsuranceSusepAnnualRecord


def _archive(files: dict[str, str]) -> bytes:
    payload = BytesIO()
    with ZipFile(payload, mode="w", compression=ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content.encode("latin1"))
    return payload.getvalue()


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
    assert "Ses_cias.csv" in CANDIDATE_SOURCE_TABLES


def test_susep_collector_lists_reads_and_inspects_exact_archive_table() -> None:
    archive = _archive(
        {
            "BaseCompleta/Ses_cias.csv": "CODIGO;NOME\n123;SEGURADORA TESTE\n",
            "BaseCompleta/README.txt": "not a table",
        }
    )
    collector = SusepSesCollector()

    assert collector.list_csv_files(archive) == ["BaseCompleta/Ses_cias.csv"]
    assert collector.find_table(archive, "ses_CIAS.csv") == "BaseCompleta/Ses_cias.csv"
    assert collector.inspect_schema(archive, "Ses_cias.csv") == ("CODIGO", "NOME")

    frame = collector.read_table(archive, "Ses_cias.csv")
    assert frame.loc[0, "CODIGO"] == 123
    assert frame.loc[0, "NOME"] == "SEGURADORA TESTE"


def test_susep_collector_fails_closed_when_exact_table_is_missing_or_ambiguous() -> None:
    collector = SusepSesCollector()
    missing = _archive({"Ses_seguros.csv": "A;B\n1;2\n"})
    ambiguous = _archive(
        {
            "a/Ses_cias.csv": "A\n1\n",
            "b/SES_CIAS.CSV": "A\n2\n",
        }
    )

    with pytest.raises(ValueError, match="found 0"):
        collector.find_table(missing, "Ses_cias.csv")
    with pytest.raises(ValueError, match="found 2"):
        collector.find_table(ambiguous, "Ses_cias.csv")


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
