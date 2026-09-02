from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_pdf_content import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_KM1_TABLE_NOT_FOUND,
    PILLAR3_PDF_REFERENCE_PERIOD_NOT_FOUND,
    PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    assess_pillar3_pdf_text,
    audit_pillar3_pdf_content,
)

_FULL_TEXT = """
Relatório de Gerenciamento de Riscos - 4T24
KM1 - Informações quantitativas sobre os requerimentos prudenciais
Índice de Capital Principal
Índice de Capital Nível I
Índice de Basileia
Razão de Alavancagem
"""


def _observation(text: str = _FULL_TEXT):
    return assess_pillar3_pdf_text(
        prudential_reference_date=date(2024, 12, 31),
        available_from=datetime(2025, 2, 6, tzinfo=UTC),
        delivery_protocol="PROTO-1",
        version=1,
        source_url="https://www.rad.cvm.gov.br/documento.pdf",
        pdf_sha256="a" * 64,
        size_bytes=100,
        page_count=10,
        extracted_text=text,
        extracted_text_sha256="b" * 64,
    )


def test_required_prudential_labels_period_and_km1_are_detected() -> None:
    observation = _observation()

    assert observation.reference_period_detected
    assert observation.km1_detected
    assert observation.missing_metric_keys == ()
    assert set(observation.found_metric_keys) == {
        "core_equity_tier1_ratio",
        "tier1_ratio",
        "basel_ratio",
        "leverage_ratio",
    }


def test_regulatory_km1_tier1_label_with_arabic_one_is_detected() -> None:
    observation = _observation(
        _FULL_TEXT.replace("Índice de Capital Nível I", "Índice de Nível 1")
    )

    assert "tier1_ratio" in observation.found_metric_keys
    assert observation.missing_metric_keys == ()


def test_missing_metric_fails_closed() -> None:
    observation = _observation(
        """
        4T24
        KM1
        Índice de Capital Principal
        Índice de Basileia
        """
    )
    audit = audit_pillar3_pdf_content(
        requested_reference_dates=[date(2024, 12, 31)],
        observations=[observation],
    )

    assert set(observation.missing_metric_keys) == {"tier1_ratio", "leverage_ratio"}
    assert PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN in audit.blockers
    assert not audit.prudential_metric_coverage_proven


def test_missing_km1_fails_closed_even_when_labels_exist() -> None:
    observation = _observation(
        """
        4T24
        Índice de Capital Principal
        Índice de Capital Nível I
        Índice de Basileia
        Razão de Alavancagem
        """
    )
    audit = audit_pillar3_pdf_content(
        requested_reference_dates=[date(2024, 12, 31)],
        observations=[observation],
    )

    assert PILLAR3_KM1_TABLE_NOT_FOUND in audit.blockers
    assert not audit.prudential_metric_coverage_proven


def test_wrong_reference_period_fails_closed() -> None:
    observation = _observation(_FULL_TEXT.replace("4T24", "4T25"))
    audit = audit_pillar3_pdf_content(
        requested_reference_dates=[date(2024, 12, 31)],
        observations=[observation],
    )

    assert not observation.reference_period_detected
    assert PILLAR3_PDF_REFERENCE_PERIOD_NOT_FOUND in audit.blockers
    assert not audit.pdf_content_validated


def test_duplicate_delivery_protocol_is_rejected() -> None:
    with pytest.raises(ValueError, match="delivery protocols must be unique"):
        audit_pillar3_pdf_content(
            requested_reference_dates=[date(2024, 12, 31)],
            observations=[_observation(), _observation()],
        )


def test_complete_pdf_evidence_never_promotes_bank_readiness() -> None:
    audit = audit_pillar3_pdf_content(
        requested_reference_dates=[date(2024, 12, 31)],
        observations=[_observation()],
    )

    assert audit.pdf_content_validated
    assert audit.prudential_metric_coverage_proven
    assert BANK_EVIDENCE_NOT_POINT_IN_TIME in audit.blockers
    assert PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN in audit.blockers
    assert not audit.revision_history_completeness_proven
    assert not audit.historical_prudential_source_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed
