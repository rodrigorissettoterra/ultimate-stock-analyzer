from pathlib import Path

from ultimate_stock_analyzer.quality.data_confidence import (
    DataConfidenceConfig,
    DataConfidenceInputs,
    analyze_data_confidence,
)

CONFIG = DataConfidenceConfig.from_yaml(Path("config/scoring/integrated_v1.4.yml"))


def test_complete_fresh_official_point_in_time_data_is_rankable() -> None:
    result = analyze_data_confidence(
        DataConfidenceInputs(
            completeness=0.95,
            freshness=0.90,
            official_source_share=0.95,
            consistency=0.90,
            point_in_time_lineage=1.0,
        ),
        config=CONFIG,
    )
    assert result.rankable
    assert result.score > 90


def test_missing_lineage_reduces_coverage_instead_of_becoming_zero() -> None:
    result = analyze_data_confidence(
        DataConfidenceInputs(
            completeness=0.95,
            freshness=0.90,
            official_source_share=0.95,
            consistency=0.90,
            point_in_time_lineage=None,
        ),
        config=CONFIG,
    )
    assert result.coverage < 1.0
    assert result.score > 80
    assert result.rankable
