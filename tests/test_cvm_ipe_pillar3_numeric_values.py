from datetime import UTC, date, datetime, timedelta

import pytest

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_numeric_values import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_CONFLICTING_SAME_TIMESTAMP,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN,
    Pillar3PrudentialObservation,
    audit_pillar3_numeric_values,
    extract_pillar3_prudential_observation,
)


def _km1_2024() -> str:
    return """
    KM1
    Índice de Capital Principal (ICP) 13,7% 13,7% 13,1% 13,0% 13,7%
    Índice de Nível 1 (%) 15,0% 15,3% 14,7% 14,5% 15,2%
    Índice de Basileia 16,5% 17,4% 16,6% 16,4% 17,0%
    Razão de Alavancagem (RA)
    RA (%) 7,4% 7,3% 7,1% 7,1% 7,4%
    """


def _observation(
    *,
    reference_date: date = date(2024, 12, 31),
    available_from: datetime = datetime(2025, 2, 6, tzinfo=UTC),
    version: int = 1,
    protocol: str = "PROTO-1",
) -> Pillar3PrudentialObservation:
    return extract_pillar3_prudential_observation(
        prudential_reference_date=reference_date,
        available_from=available_from,
        delivery_protocol=protocol,
        version=version,
        source_url="https://www.rad.cvm.gov.br/documento.pdf",
        pdf_sha256="a" * 64,
        page_texts=[_km1_2024()],
    )


def test_extracts_current_t_column_from_validated_km1_rows() -> None:
    observation = _observation()

    assert observation.core_equity_tier1_ratio == pytest.approx(0.137)
    assert observation.tier1_ratio == pytest.approx(0.150)
    assert observation.basel_ratio == pytest.approx(0.165)
    assert observation.leverage_ratio == pytest.approx(0.074)
    assert observation.observed_filing_point_in_time_eligible


def test_extracts_2025_current_values_and_deduplicates_equivalent_rows() -> None:
    page = """
    KM1
    Índice de Capital Principal (ICP) 12,3% 13,5% 13,4% 13,1% 13,7%
    Índice de Nível 1 (%) 13,8% 14,8% 14,7% 14,5% 15,0%
    Índice de Basileia 15,2% 16,4% 16,5% 15,7% 16,5%
    Índice de Basileia, considerando: 15,2% 16,4% 16,5% 15,7% 16,5%
    Razão de Alavancagem (RA)
    RA (%) 7,0% 7,4% 7,5% 7,5% 7,4%
    """
    observation = extract_pillar3_prudential_observation(
        prudential_reference_date=date(2025, 12, 31),
        available_from=datetime(2026, 2, 5, tzinfo=UTC),
        delivery_protocol="PROTO-2025",
        version=1,
        source_url="https://www.rad.cvm.gov.br/documento.pdf",
        pdf_sha256="b" * 64,
        page_texts=[page],
    )

    assert observation.values() == pytest.approx(
        {
            "core_equity_tier1_ratio": 0.123,
            "tier1_ratio": 0.138,
            "basel_ratio": 0.152,
            "leverage_ratio": 0.070,
        }
    )


def test_row_without_five_period_values_fails_closed() -> None:
    page = _km1_2024().replace(
        "RA (%) 7,4% 7,3% 7,1% 7,1% 7,4%",
        "RA (%) 7,4% 7,3%",
    )

    with pytest.raises(ValueError, match="missing=leverage_ratio"):
        extract_pillar3_prudential_observation(
            prudential_reference_date=date(2024, 12, 31),
            available_from=datetime(2025, 2, 6, tzinfo=UTC),
            delivery_protocol="PROTO-MISSING",
            version=1,
            source_url="https://www.rad.cvm.gov.br/documento.pdf",
            pdf_sha256="c" * 64,
            page_texts=[page],
        )


def test_conflicting_candidate_rows_fail_closed() -> None:
    page = _km1_2024() + "\nÍndice de Basileia 16,4% 17,4% 16,6% 16,4% 17,0%"

    with pytest.raises(ValueError, match="ambiguous=basel_ratio"):
        extract_pillar3_prudential_observation(
            prudential_reference_date=date(2024, 12, 31),
            available_from=datetime(2025, 2, 6, tzinfo=UTC),
            delivery_protocol="PROTO-AMBIGUOUS",
            version=1,
            source_url="https://www.rad.cvm.gov.br/documento.pdf",
            pdf_sha256="d" * 64,
            page_texts=[page],
        )


def test_timeline_selects_latest_observed_version_available_as_of() -> None:
    first = _observation()
    second = _observation(
        available_from=datetime(2025, 4, 1, tzinfo=UTC),
        version=2,
        protocol="PROTO-2",
    )
    audit = audit_pillar3_numeric_values([second, first])

    assert audit.numeric_extraction_contract_ready
    assert audit.value_as_of(
        reference_date=date(2024, 12, 31),
        as_of=datetime(2025, 2, 5, tzinfo=UTC),
    ) is None
    assert (
        audit.value_as_of(
            reference_date=date(2024, 12, 31),
            as_of=datetime(2025, 3, 31, tzinfo=UTC),
        )
        == first
    )
    assert (
        audit.value_as_of(
            reference_date=date(2024, 12, 31),
            as_of=datetime(2025, 4, 1, tzinfo=UTC),
        )
        == second
    )
    assert {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }.issubset(audit.blockers)
    assert PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN not in audit.blockers
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed


def test_conflicting_same_timestamp_keeps_numeric_contract_fail_closed() -> None:
    first = _observation()
    conflicting = Pillar3PrudentialObservation(
        prudential_reference_date=first.prudential_reference_date,
        available_from=first.available_from,
        delivery_protocol="PROTO-CONFLICT",
        version=2,
        source_url=first.source_url,
        pdf_sha256="e" * 64,
        core_equity_tier1_ratio=first.core_equity_tier1_ratio,
        tier1_ratio=first.tier1_ratio,
        basel_ratio=first.basel_ratio - 0.001,
        leverage_ratio=first.leverage_ratio,
    )

    audit = audit_pillar3_numeric_values([first, conflicting])

    assert PILLAR3_CONFLICTING_SAME_TIMESTAMP in audit.blockers
    assert PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN in audit.blockers
    assert not audit.numeric_extraction_contract_ready


def test_duplicate_protocol_is_rejected() -> None:
    first = _observation()
    duplicate = _observation(
        available_from=first.available_from + timedelta(days=1),
        version=2,
    )

    with pytest.raises(ValueError, match="delivery protocols must be unique"):
        audit_pillar3_numeric_values([first, duplicate])
