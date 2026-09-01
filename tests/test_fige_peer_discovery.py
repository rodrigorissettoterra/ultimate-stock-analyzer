from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_FINANCIAL_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.scoring.fige_peer_discovery import (
    compare_fige_financial_schema,
    discover_fige_classification_candidates,
    evaluate_fige_peer_discovery,
    schema_audit_company_ids,
)
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelDefinition,
    SectorModelRegistry,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)


def _record(
    company_id: str,
    cvm_code: int,
    issuer_code: str,
    *,
    sector: str = "Financeiro",
    subsector: str = "Intermediarios Financeiros",
    segment: str = "Intermediacao Financeira",
) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector=sector,
        subsector=subsector,
        segment=segment,
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _registry() -> SectorModelRegistry:
    return SectorModelRegistry(
        version="test",
        default_model=SectorModelDefinition(
            model_id="general_corporate",
            config_path=Path("general.yml"),
        ),
        models=(
            SectorModelDefinition(
                model_id="banks",
                config_path=Path("banks.yml"),
                priority=100,
                segment_contains=("banco",),
            ),
        ),
    )


def _report(
    company_id: str,
    *,
    missing: set[str] | None = None,
    mismatched: set[str] | None = None,
) -> FinancialStatementTreeAuditReport:
    missing = missing or set()
    mismatched = mismatched or set()
    lines = []
    for binding in FIGE_FINANCIAL_ACCOUNT_BINDINGS:
        if binding.concept_id in missing:
            continue
        label = (
            f"{binding.expected_label} ALTERADO"
            if binding.concept_id in mismatched
            else binding.expected_label
        )
        lines.append(
            StatementTreeLine(
                statement=binding.statement,
                account_code=binding.account_code,
                account_name=label,
                value_brl=1.0,
                depth=len(binding.account_code.split(".")),
                consolidation_scope="INDIVIDUAL",
                document_type="DFP",
                version=1,
                document_id=1,
            )
        )
    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=datetime(2025, 12, 31, tzinfo=UTC).date(),
        max_depth=4,
        statement_counts={},
        lines=tuple(lines),
    )


def test_discovery_limits_schema_audit_to_near_fallback_candidates() -> None:
    records = [
        _record("cvm:6041", 6041, "FIGE"),
        _record("cvm:100", 100, "PEER"),
        _record("cvm:200", 200, "SUBS", segment="Servicos Financeiros"),
        _record("cvm:300", 300, "BANK", segment="Banco Comercial"),
        _record(
            "cvm:400",
            400,
            "WIDE",
            subsector="Previdencia e Seguros",
            segment="Seguros",
        ),
        _record(
            "cvm:500",
            500,
            "OUT",
            sector="Bens Industriais",
            subsector="Maquinas",
            segment="Equipamentos",
        ),
    ]
    anchor, candidates = discover_fige_classification_candidates(
        records,
        registry=_registry(),
    )

    assert anchor.company_id == "cvm:6041"
    by_id = {candidate.company_id: candidate for candidate in candidates}
    assert by_id["cvm:100"].peer_scope == "EXACT_SEGMENT"
    assert by_id["cvm:200"].peer_scope == "SAME_SUBSECTOR"
    assert by_id["cvm:300"].disposition == "EXCLUDED_SPECIALIZED_MODEL"
    assert by_id["cvm:400"].disposition == "CONTEXT_ONLY_BROADER_SCOPE"
    assert "cvm:500" not in by_id
    assert schema_audit_company_ids(candidates) == ("cvm:100", "cvm:200")


def test_schema_matching_requires_exact_code_and_label_for_primary_concepts() -> None:
    exact = compare_fige_financial_schema(_report("cvm:100"))
    assert exact.primary_schema_coverage == 1.0
    assert exact.total_schema_coverage == 1.0
    assert exact.exact_schema_match is True

    mismatch = compare_fige_financial_schema(
        _report("cvm:100", mismatched={"other_operating_result"})
    )
    assert mismatch.primary_schema_coverage < 1.0
    assert mismatch.exact_schema_match is False
    assert mismatch.label_mismatch_concepts == ("other_operating_result",)


def test_peer_discovery_never_approves_peer_set_or_scoring() -> None:
    records = [
        _record("cvm:6041", 6041, "FIGE"),
        _record("cvm:100", 100, "PEER"),
        _record("cvm:200", 200, "MISS"),
    ]
    anchor, candidates = discover_fige_classification_candidates(
        records,
        registry=_registry(),
    )
    report = evaluate_fige_peer_discovery(
        anchor=anchor,
        candidates=candidates,
        statement_reports={
            "cvm:6041": _report("cvm:6041"),
            "cvm:100": _report("cvm:100"),
            "cvm:200": _report("cvm:200", missing={"pretax_income"}),
        },
        min_comparable_peers_for_cross_sectional_score=8,
    )

    assert report.history_validation_candidate_company_ids == ("cvm:100",)
    assert report.potential_peer_count_including_fige == 2
    assert report.cross_sectional_minimum_reachable_in_current_scope is False
    assert report.status == "INSUFFICIENT_SCHEMA_CANDIDATES_WITHIN_CURRENT_B3_SUBSECTOR"
    assert report.peer_set_ready is False
    assert report.scoring_ready is False
    assert report.routing_ready is False
    assert report.applicability_registry_resolvable is False


def test_anchor_schema_drift_fails_closed() -> None:
    records = [_record("cvm:6041", 6041, "FIGE")]
    anchor, candidates = discover_fige_classification_candidates(
        records,
        registry=_registry(),
    )

    try:
        evaluate_fige_peer_discovery(
            anchor=anchor,
            candidates=candidates,
            statement_reports={
                "cvm:6041": _report(
                    "cvm:6041",
                    mismatched={"gross_financial_intermediation_result"},
                )
            },
            min_comparable_peers_for_cross_sectional_score=8,
        )
    except ValueError as exc:
        assert "no longer exactly matches" in str(exc)
    else:
        raise AssertionError("Expected FIGE anchor schema drift to fail closed")
