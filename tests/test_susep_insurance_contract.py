from datetime import UTC, date, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest

from ultimate_stock_analyzer.collectors import susep_ses as susep_ses_module
from ultimate_stock_analyzer.collectors.susep_ses import (
    CANDIDATE_SOURCE_TABLES,
    SUSEP_SES_DOWNLOAD_URL,
    SUSEP_SES_TABLE_DOCUMENTATION_URL,
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
    assert contract.table_documentation_url == SUSEP_SES_TABLE_DOCUMENTATION_URL
    assert "Ses_cias.csv" in CANDIDATE_SOURCE_TABLES


def test_susep_download_retries_transient_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, url: str, **_: object) -> httpx.Response:
            calls.append(url)
            request = httpx.Request("GET", url)
            if len(calls) == 1:
                raise httpx.ConnectTimeout("temporary timeout", request=request)
            return httpx.Response(200, content=b"official-payload", request=request)

    monkeypatch.setattr(susep_ses_module.httpx, "Client", FakeClient)
    collector = SusepSesCollector(retry_attempts=2, retry_backoff_seconds=0)

    assert collector.download_archive_bytes() == b"official-payload"
    assert calls == [SUSEP_SES_DOWNLOAD_URL, SUSEP_SES_DOWNLOAD_URL]


def test_susep_download_fails_closed_after_retry_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class FailingClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "FailingClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, url: str, **_: object) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectTimeout(
                "persistent timeout",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(susep_ses_module.httpx, "Client", FailingClient)
    collector = SusepSesCollector(retry_attempts=3, retry_backoff_seconds=0)

    with pytest.raises(httpx.ConnectTimeout):
        collector.download_archive_bytes()
    assert calls == 3


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


def test_candidate_schema_manifest_records_presence_without_promoting_semantics() -> None:
    archive = _archive(
        {
            "BaseCompleta/Ses_cias.csv": "CODIGO;NOME\n123;SEGURADORA TESTE\n",
            "BaseCompleta/Ses_seguros.csv": "MES;PREMIO;SINISTRO\n202501;10;5\n",
            "BaseCompleta/other.csv": "A\n1\n",
        }
    )
    manifest = SusepSesCollector().candidate_schema_manifest(archive)

    assert manifest["source"] == "SUSEP_SES"
    assert manifest["point_in_time_eligible"] is False
    assert manifest["csv_file_count"] == 3
    tables = manifest["tables"]
    assert isinstance(tables, dict)
    assert tables["Ses_cias.csv"] == {
        "present": True,
        "archive_path": "BaseCompleta/Ses_cias.csv",
        "columns": ["CODIGO", "NOME"],
    }
    assert tables["Ses_pl_margem.csv"] == {
        "present": False,
        "archive_path": None,
        "columns": [],
    }


def test_documentation_manifest_extracts_only_bounded_exact_field_evidence() -> None:
    documentation = (
        r"{\rtf1\ansi "
        r"Ses_seguros.csv\par "
        r"damesano Ano e m\'eas da informa\'e7\'e3o\par "
        r"premio_ganho Pr\'eamio Ganho (R$)\par "
        r"sinistro_ocorrido Sinistros Ocorridos (R$)\par "
        r"desp_com Despesa Comercial (R$)\par "
        r"}"
    ).encode("latin1")
    manifest = SusepSesCollector().documentation_field_manifest(
        documentation,
        fields=("damesano", "premio_ganho", "sinistro_ocorrido", "missing_field"),
        context_chars=80,
    )

    assert manifest["source"] == "SUSEP_SES_TABLE_DOCUMENTATION"
    assert manifest["source_url"] == SUSEP_SES_TABLE_DOCUMENTATION_URL
    fields = manifest["fields"]
    assert isinstance(fields, dict)
    assert fields["damesano"]["present"] is True
    assert fields["premio_ganho"]["present"] is True
    assert fields["sinistro_ocorrido"]["present"] is True
    assert fields["missing_field"] == {
        "present": False,
        "occurrences": 0,
        "snippets": [],
    }
    assert "Prêmio Ganho" in fields["premio_ganho"]["snippets"][0]


def test_documentation_manifest_rejects_unbounded_context() -> None:
    with pytest.raises(ValueError, match="at least 40"):
        SusepSesCollector().documentation_field_manifest(b"{\\rtf1 test}", context_chars=20)


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
