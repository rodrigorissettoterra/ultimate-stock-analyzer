from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_HOLDING_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.scoring.itsa_peer_discovery import (
    compare_itsa_holding_schema,
    discover_itsa_exact_segment_candidates,
    evaluate_itsa_peer_discovery,
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
    subsector: str = "Holdings Diversificadas",
    segment: str = "Holdings Diversificadas",
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


def _registry(*, specialized_holding_route: bool = False) -> SectorModelRegistry:
    models = ()
    if specialized_holding_route:
        models = (
            SectorModelDefinition(
                model_id="future_holding_model",
                config_path=Path("holding.yml"),
                priority=100,
                segment_contains=("holdings diversificadas",),
            ),
        )
    return SectorModelRegistry(
        version="test",
        default_model=SectorModelDefinition(
            model_id="general_corporate",
            config_path=Path("general.yml"),
        ),
        models=models,
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
    for binding in ITSA_HOLDING_ACCOUNT_BINDINGS:
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
        reference_date=date(2025, 12, 31),
        max_depth=6,
        statement_counts={},
        lines=tuple(lines),
    )


def test_discovery_uses_only_itsa_exact_b3_segment() -> None:
    records = [
        _record("cvm:7617", 7617, "ITSA"),
        _record("cvm:100", 100, "PEER"),
        _record(
            "cvm:200",
            200,
            "OTHER",
            subsector="Serviços Financeiros Diversos",
            segment="Gestão de Recursos e Investimentos",
        ),
        _record(
            "cvm:300",
            300,
            "OUT",
            sector="Bens Industriais",
            subsector="Máquinas e Equipamentos",
            segment="Máquinas e Equipamentos",
        ),
    ]

    anchor, candidates = discover_itsa_exact_segment_candidates(
        records,
        registry=_registry(),
    )

    assert anchor.company_id == "cvm:7617"
    assert tuple(item.company_id for item in candidates) == ("cvm:100",)


def test_exact_segment_candidate_survives_future_specialized_routing() -> None:
    records = [
        _record("cvm:7617", 7617, "ITSA"),
        _record("cvm:100", 100, "PEER"),
    ]

    anchor, candidates = discover_itsa_exact_segment_candidates(
        records,
        registry=_registry(specialized_holding_route=True),
    )

    assert anchor.model_id == "future_holding_model"
    assert len(candidates) == 1
    assert candidates[0].company_id == "cvm:100"
    assert candidates[0].model_id == "future_holding_model"


def test_schema_comparison_requires_exact_critical_code_and_label() -> None:
    exact = compare_itsa_holding_schema(_report("cvm:100"))
    assert exact.critical_schema_coverage == 1.0
    assert exact.total_schema_coverage == 1.0
    assert exact.exact_schema_match is True

    critical_mismatch = compare_itsa_holding_schema(
        _report("cvm:100", mismatched={"investments_total"})
    )
    assert critical_mismatch.critical_schema_coverage < 1.0
    assert critical_mismatch.exact_schema_match is False

    supporting_missing = compare_itsa_holding_schema(
        _report("cvm:100", missing={"other_investments"})
    )
    assert supporting_missing.critical_schema_coverage == 1.0
    assert supporting_missing.total_schema_coverage < 1.0


def test_peer_discovery_keeps_cross_sectional_gate_closed_when_segment_is_too_small() -> None:
    records = [
        _record("cvm:7617", 7617, "ITSA"),
        _record("cvm:100", 100, "AAAA"),
        _record("cvm:200", 200, "BBBB"),
        _record("cvm:300", 300, "CCCC"),
    ]
    anchor, candidates = discover_itsa_exact_segment_candidates(
        records,
        registry=_registry(),
    )

    report = evaluate_itsa_peer_discovery(
        anchor=anchor,
        candidates=candidates,
        statement_reports={
            "cvm:7617": _report("cvm:7617"),
            "cvm:100": _report("cvm:100"),
            "cvm:200": _report("cvm:200", missing={"other_investments"}),
            "cvm:300": _report("cvm:300", mismatched={"equity_method_result"}),
        },
        min_comparable_peers_for_cross_sectional_score=8,
    )

    assert report.exact_segment_company_count_including_itsa == 4
    assert report.exact_segment_numerical_minimum_reachable is False
    assert report.history_validation_candidate_company_ids == ("cvm:100", "cvm:200")
    assert report.potential_peer_count_including_itsa == 3
    assert report.cross_sectional_minimum_reachable_after_schema is False
    assert report.status == "CROSS_SECTIONAL_MINIMUM_UNREACHABLE_IN_CURRENT_EXACT_B3_SEGMENT"
    assert report.peer_set_ready is False
    assert report.scoring_ready is False
    assert report.routing_ready is False
    assert report.applicability_registry_resolvable is False


def test_anchor_contract_drift_fails_closed() -> None:
    records = [_record("cvm:7617", 7617, "ITSA")]
    anchor, candidates = discover_itsa_exact_segment_candidates(
        records,
        registry=_registry(),
    )

    try:
        evaluate_itsa_peer_discovery(
            anchor=anchor,
            candidates=candidates,
            statement_reports={
                "cvm:7617": _report(
                    "cvm:7617",
                    mismatched={"net_income_parent"},
                )
            },
            min_comparable_peers_for_cross_sectional_score=8,
        )
    except ValueError as exc:
        assert "no longer exactly matches" in str(exc)
    else:
        raise AssertionError("Expected ITSA accounting-contract drift to fail closed")
