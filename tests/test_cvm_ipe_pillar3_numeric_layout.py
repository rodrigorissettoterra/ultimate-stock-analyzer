from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_numeric_layout import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_METRIC_CONTEXT_NOT_FOUND,
    PILLAR3_METRIC_NUMERIC_CANDIDATE_NOT_FOUND,
    PILLAR3_NUMERIC_LAYOUT_UNPROVEN,
    audit_pillar3_numeric_layout,
    inspect_pillar3_document_layout,
)


def _document(page_texts: list[str]):
    return inspect_pillar3_document_layout(
        prudential_reference_date=date(2024, 12, 31),
        available_from=datetime(2025, 2, 6, tzinfo=UTC),
        delivery_protocol="PROTO-1",
        version=1,
        source_url="https://www.rad.cvm.gov.br/documento.pdf",
        pdf_sha256="a" * 64,
        page_texts=page_texts,
        context_radius_lines=2,
    )


def test_metric_contexts_preserve_numeric_tokens() -> None:
    document = _document(
        [
            """
            KM1
            Índice de Capital Principal 13,7%
            Índice de Nível 1 15,0%
            Índice de Basileia 16,5%
            """,
            """
            LR2
            Razão de Alavancagem 7,8%
            """,
        ]
    )

    by_key = {item.metric_key: item for item in document.metric_evidence}
    assert by_key["core_equity_tier1_ratio"].numeric_tokens
    assert "13.7" in by_key["core_equity_tier1_ratio"].numeric_tokens
    assert "15.0" in by_key["tier1_ratio"].numeric_tokens
    assert "16.5" in by_key["basel_ratio"].numeric_tokens
    assert "7.8" in by_key["leverage_ratio"].numeric_tokens
    assert document.missing_metric_keys == ()
    assert document.metrics_without_numeric_candidates == ()


def test_prefers_later_numeric_table_match_over_earlier_toc_match() -> None:
    document = _document(
        [
            "Índice de Basileia",
            """
            KM1
            Índice de Capital Principal 13,7%
            Índice de Nível 1 15,0%
            Índice de Basileia 16,5%
            Razão de Alavancagem 7,8%
            """,
        ]
    )

    basel = next(
        item for item in document.metric_evidence if item.metric_key == "basel_ratio"
    )
    assert basel.page_number == 2
    assert "16.5" in basel.numeric_tokens


def test_missing_context_and_numeric_candidate_fail_closed() -> None:
    document = _document(
        [
            """
            Índice de Capital Principal
            Índice de Nível 1 15,0%
            Índice de Basileia 16,5%
            """
        ]
    )
    audit = audit_pillar3_numeric_layout([document])

    assert "leverage_ratio" in document.missing_metric_keys
    assert "core_equity_tier1_ratio" not in document.metrics_without_numeric_candidates
    assert PILLAR3_METRIC_CONTEXT_NOT_FOUND in audit.blockers
    assert PILLAR3_METRIC_NUMERIC_CANDIDATE_NOT_FOUND in audit.blockers


def test_diagnostic_never_promotes_numeric_or_bank_readiness() -> None:
    document = _document(
        [
            """
            Índice de Capital Principal 13,7%
            Índice de Nível 1 15,0%
            Índice de Basileia 16,5%
            Razão de Alavancagem 7,8%
            """
        ]
    )
    audit = audit_pillar3_numeric_layout([document])

    assert audit.all_metric_contexts_observed
    assert audit.all_metric_contexts_have_numeric_candidates
    assert {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_NUMERIC_LAYOUT_UNPROVEN,
    }.issubset(audit.blockers)
    assert not audit.numeric_extraction_contract_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed


def test_duplicate_protocol_is_rejected() -> None:
    document = _document(["Índice de Capital Principal 13,7%"])
    with pytest.raises(ValueError, match="delivery protocols must be unique"):
        audit_pillar3_numeric_layout([document, document])
