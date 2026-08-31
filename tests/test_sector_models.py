from pathlib import Path

import pytest

from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelRegistry,
    SectorStructuralScoringEngine,
)

REGISTRY = Path("config/scoring/sector_registry_v0.6.yml")


def _bank_row(ticker: str, scale: float) -> dict[str, float | str]:
    return {
        "ticker": ticker,
        "sector": "Financials",
        "subsector": "Bancos",
        "roe": 0.12 * scale,
        "roa": 0.012 * scale,
        "net_interest_margin": 0.035 * scale,
        "npl_90d_ratio": 0.06 / scale,
        "cost_of_credit": 0.045 / scale,
        "npl_coverage": 1.2 * scale,
        "basel_ratio": 0.12 + 0.01 * scale,
        "tier1_ratio": 0.10 + 0.008 * scale,
        "equity_to_assets": 0.08 + 0.005 * scale,
        "efficiency_ratio": 0.65 / scale,
        "fee_income_share": 0.20 * scale,
        "loan_cagr_5y": 0.04 * scale,
        "net_income_cagr_5y": 0.03 * scale,
        "dividend_regularity": 55.0 + 5.0 * scale,
        "dividend_sustainability": 55.0 + 5.0 * scale,
        "dividend_cagr_5y": 0.02 * scale,
        "net_debt_ebitda": 100.0 / scale,
    }


def test_registry_routes_sector_specific_models_and_normalizes_accents() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)

    assert registry.select(
        {"ticker": "BANK3", "sector": "Financeiro", "subsector": "Bancos"}
    ).model_id == "banks"
    assert registry.select(
        {"ticker": "INSU3", "sector": "Financeiro", "subsector": "Seguradoras"}
    ).model_id == "insurance"
    assert registry.select(
        {"ticker": "UTIL3", "sector": "Utilidade Pública", "subsector": "Energia Elétrica"}
    ).model_id == "utilities"
    assert registry.select(
        {"ticker": "MINE3", "sector": "Materiais", "subsector": "Mineração"}
    ).model_id == "commodities"

    fallback = registry.select(
        {"ticker": "TECH3", "sector": "Technology", "subsector": "Software"}
    )
    assert fallback.model_id == "general_corporate"
    assert fallback.is_fallback
    assert fallback.reason == "default_fallback"


def test_b3_gas_utility_does_not_overlap_commodity_model() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    row = {
        "ticker": "GAS3",
        "sector": "Utilidade Pública",
        "subsector": "Gás",
        "segment": "Gás",
    }

    assert registry.select(row).model_id == "utilities"
    matches = [
        model.model_id
        for model in registry.models
        if model.match_reason(row) is not None
    ]
    assert matches == ["utilities"]


def test_banks_use_bank_model_and_ignore_corporate_leverage_metric() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    engine = SectorStructuralScoringEngine(registry)
    rows = [_bank_row(f"BNK{index}", float(index)) for index in range(1, 9)]

    baseline = engine.score_universe(rows)
    changed = [dict(row) for row in rows]
    changed[-1]["net_debt_ebitda"] = -999.0
    rescored = engine.score_universe(changed)

    baseline_map = {result.ticker: result for result in baseline}
    rescored_map = {result.ticker: result for result in rescored}
    best = baseline_map["BNK8"]

    assert best.model_id == "banks"
    assert best.model_family == "bank_v1"
    assert best.peer_group == "banks"
    assert best.rankable
    assert {"asset_quality", "capital", "efficiency"} <= set(best.categories)
    assert "financial_strength" not in best.categories
    assert best.structural_score == pytest.approx(rescored_map["BNK8"].structural_score)


def test_bank_and_insurance_are_never_compared_in_same_peer_group() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)

    bank = registry.select(
        {"ticker": "BANK3", "sector": "Financials", "subsector": "Banks"}
    )
    insurer = registry.select(
        {"ticker": "INSU3", "sector": "Financials", "subsector": "Insurance"}
    )

    assert bank.model_id == "banks"
    assert insurer.model_id == "insurance"
    assert bank.peer_group == "banks"
    assert insurer.peer_group == "insurance"


def test_commodity_peer_group_prefers_subsector() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    selection = registry.select(
        {
            "ticker": "OIL3",
            "sector": "Materials",
            "subsector": "Oil & Gas",
            "segment": "Exploration",
        }
    )

    assert selection.model_id == "commodities"
    assert selection.peer_group == "Oil & Gas"


def test_duplicate_ticker_is_rejected_before_scoring() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    engine = SectorStructuralScoringEngine(registry)
    row = _bank_row("DUPL3", 1.0)

    with pytest.raises(ValueError, match="duplicate ticker"):
        engine.score_universe([row, dict(row)])
