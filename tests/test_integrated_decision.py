from pathlib import Path

from ultimate_stock_analyzer.quality.data_confidence import (
    DataConfidenceConfig,
    DataConfidenceInputs,
    analyze_data_confidence,
)
from ultimate_stock_analyzer.scoring.integrated import (
    DecisionStatus,
    IntegratedConfig,
    IntegratedInputs,
    ScoreInput,
    analyze_integrated_decision,
)

CONFIG_PATH = Path("config/scoring/integrated_v1.4.yml")
CONFIG = IntegratedConfig.from_yaml(CONFIG_PATH)
DATA_CONFIG = DataConfidenceConfig.from_yaml(CONFIG_PATH)


def _data_confidence(*, good: bool = True):
    value = 0.95 if good else 0.40
    return analyze_data_confidence(
        DataConfidenceInputs(
            completeness=value,
            freshness=value,
            official_source_share=value,
            consistency=value,
            point_in_time_lineage=value,
        ),
        config=DATA_CONFIG,
    )


def _inputs(
    *,
    structural: float = 90.0,
    valuation: float = 85.0,
    entry: float = 80.0,
    data_good: bool = True,
    blocked: bool = False,
) -> IntegratedInputs:
    return IntegratedInputs(
        structural=ScoreInput(structural, 0.95),
        accounting_quality=ScoreInput(85.0, 0.90),
        governance=ScoreInput(82.0, 0.90),
        audit_risk_score=ScoreInput(10.0, 0.95),
        valuation=ScoreInput(valuation, 0.90),
        news=ScoreInput(70.0, 0.80),
        macro=ScoreInput(60.0, 0.75),
        risk_safety=ScoreInput(75.0, 0.90),
        liquidity=ScoreInput(80.0, 0.95),
        lending_net=ScoreInput(65.0, 0.80),
        entry=ScoreInput(entry, 0.90),
        data_confidence=_data_confidence(good=data_good),
        audit_blocked=blocked,
    )


def test_three_answers_remain_separate_for_attractive_current_opportunity() -> None:
    result = analyze_integrated_decision(_inputs(), config=CONFIG)
    assert result.rankable
    assert result.status == DecisionStatus.VERY_ATTRACTIVE
    assert result.ranking_score == result.investment_attractiveness_score
    assert result.actionability_score != result.company_quality_score


def test_good_company_can_be_wait_when_entry_is_stretched() -> None:
    result = analyze_integrated_decision(_inputs(entry=25.0), config=CONFIG)
    assert result.company_quality_score > 75
    assert result.investment_attractiveness_score > 70
    assert result.entry_timing_score == 25.0
    assert result.status == DecisionStatus.WAIT


def test_weak_structural_quality_cannot_become_attractive_from_context_alone() -> None:
    result = analyze_integrated_decision(_inputs(structural=20.0, valuation=100.0, entry=100.0), config=CONFIG)
    assert result.company_quality_score < 65
    assert result.status not in {DecisionStatus.ATTRACTIVE, DecisionStatus.VERY_ATTRACTIVE}


def test_blocking_event_overrides_high_scores() -> None:
    result = analyze_integrated_decision(_inputs(blocked=True), config=CONFIG)
    assert not result.rankable
    assert result.status == DecisionStatus.BLOCKED


def test_low_data_confidence_abstains() -> None:
    result = analyze_integrated_decision(_inputs(data_good=False), config=CONFIG)
    assert not result.rankable
    assert result.status == DecisionStatus.INCONCLUSIVE
