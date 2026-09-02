import io
import zipfile
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.cvm_ipe_corporate_action_ledger import (
    CVM_IPE_DOCUMENTS_UNSTRUCTURED,
    CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN,
    EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE,
    EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND,
    STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN,
    UNSUPPORTED_SUBSCRIPTION_RIGHTS,
    audit_cvm_ipe_corporate_action_ledger,
)
from ultimate_stock_analyzer.collectors.cvm_ipe import parse_cvm_ipe_zip

_HEADER = ";".join(
    [
        "CNPJ_Companhia",
        "Nome_Companhia",
        "Codigo_CVM",
        "Data_Referencia",
        "Categoria",
        "Tipo",
        "Especie",
        "Assunto",
        "Data_Entrega",
        "Tipo_Apresentacao",
        "Protocolo_Entrega",
        "Versao",
        "Link_Download",
    ]
)


def _archive(*rows: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("ipe_cia_aberta_2025.csv", _HEADER + "\n" + "\n".join(rows))
    return output.getvalue()


def _row(
    *,
    code: str = "1234",
    reference_date: str = "2025-02-10",
    delivered_on: str = "2025-02-10",
    category: str = "Fato Relevante",
    subject: str = "Unrelated text is deliberately not interpreted",
    link: str = "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?id=1",
) -> str:
    return ";".join(
        [
            "00.000.000/0001-00",
            "TESTE S.A.",
            code,
            reference_date,
            category,
            "",
            "",
            subject,
            delivered_on,
            "AP - Apresentação",
            "001234IPE100220250100000001-00",
            "1",
            link,
        ]
    )


def _payload() -> dict[str, object]:
    return {
        "stockDividends": [
            {
                "label": "Bonificação",
                "assetIssued": "BRTESTACNOR0",
                "isinCode": "BRTESTACNOR0",
                "approvedOn": "2025-02-10",
                "lastDatePrior": "2025-02-17",
            },
            {
                "label": "Grupamento",
                "assetIssued": "BRTESTACNOR0",
                "isinCode": "BRTESTACNOR0",
                "approvedOn": "2025-03-01",
                "lastDatePrior": "2025-03-05",
            },
        ],
        "cashDividends": [],
        "subscriptions": [
            {
                "label": "Subscrição",
                "assetIssued": "BRTESTACNOR0",
                "isinCode": "BRTESTACNOR0",
                "approvedOn": "2025-02-10",
                "lastDatePrior": "2025-02-17",
            }
        ],
    }


def test_cvm_ipe_parser_filters_identity_and_assigns_conservative_availability() -> None:
    documents = parse_cvm_ipe_zip(
        _archive(
            _row(),
            _row(code="9999", reference_date="not-a-date"),
        ),
        year=2025,
        cvm_codes={1234},
    )

    assert len(documents) == 1
    document = documents[0]
    assert document.company_id == "cvm:1234"
    assert document.reference_date == date(2025, 2, 10)
    assert document.delivered_on == date(2025, 2, 10)
    assert document.available_from == datetime(2025, 2, 11, tzinfo=UTC)


def test_cvm_ipe_parser_fails_closed_on_target_row_and_schema_errors() -> None:
    with pytest.raises(ValueError, match="invalid CVM IPE target row"):
        parse_cvm_ipe_zip(
            _archive(_row(reference_date="not-a-date")),
            year=2025,
            cvm_codes={1234},
        )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("ipe.csv", "Codigo_CVM;Data_Referencia\n1234;2025-01-01")
    with pytest.raises(ValueError, match="schema missing required columns"):
        parse_cvm_ipe_zip(output.getvalue(), year=2025, cvm_codes={1234})


def test_ledger_uses_exact_identity_and_reference_date_without_subject_inference() -> None:
    documents = parse_cvm_ipe_zip(
        _archive(
            _row(subject="Text does not name a bonus"),
            _row(category="Reunião da Administração", subject="Different text"),
        ),
        year=2025,
        cvm_codes={1234},
    )
    audit = audit_cvm_ipe_corporate_action_ledger(
        issuing_company="TEST",
        ticker="TEST3",
        cvm_code=1234,
        b3_payload=_payload(),
        documents=documents,
        source_years=(2025,),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert audit.observed_event_count == 3
    assert audit.events_with_same_reference_date_documents == 2
    assert audit.events_with_documents_available_by_com == 2
    assert audit.exact_reference_date_candidate_count == 4
    assert not audit.observed_event_document_corroboration_complete
    assert EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND in audit.blockers
    assert UNSUPPORTED_SUBSCRIPTION_RIGHTS in audit.blockers


def test_same_day_delivery_is_not_treated_as_known_during_com_session() -> None:
    payload = _payload()
    stock = payload["stockDividends"]
    assert isinstance(stock, list)
    stock[0]["lastDatePrior"] = "2025-02-10"
    stock.pop()
    payload["subscriptions"] = []
    documents = parse_cvm_ipe_zip(
        _archive(_row()),
        year=2025,
        cvm_codes={1234},
    )
    audit = audit_cvm_ipe_corporate_action_ledger(
        issuing_company="TEST",
        ticker="TEST3",
        cvm_code=1234,
        b3_payload=payload,
        documents=documents,
        source_years=(2025,),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert audit.events_with_same_reference_date_documents == 1
    assert audit.events_with_documents_available_by_com == 0
    assert EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE in audit.blockers


def test_document_corroboration_never_promotes_structured_event_readiness() -> None:
    documents = parse_cvm_ipe_zip(
        _archive(_row()),
        year=2025,
        cvm_codes={1234},
    )
    audit = audit_cvm_ipe_corporate_action_ledger(
        issuing_company="TEST",
        ticker="TEST3",
        cvm_code=1234,
        b3_payload={
            "stockDividends": [
                {
                    "label": "Bonificação",
                    "approvedOn": "2025-02-10",
                    "lastDatePrior": "2025-02-17",
                }
            ],
            "cashDividends": [],
            "subscriptions": [],
        },
        documents=documents,
        source_years=(2025,),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert audit.observed_event_document_corroboration_complete
    assert audit.observed_event_pit_document_corroboration_complete
    assert audit.historical_document_archive_available
    assert CVM_IPE_DOCUMENTS_UNSTRUCTURED in audit.blockers
    assert CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN in audit.blockers
    assert STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN in audit.blockers
    assert not audit.structured_event_terms_available
    assert not audit.security_class_resolution_proven
    assert not audit.historical_event_source_completeness_proven
    assert not audit.event_aware_return_path_ready
    assert not audit.readiness_promotion_allowed
    assert not audit.price_series_blocker_removed
