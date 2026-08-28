from datetime import date
from pathlib import Path

from ultimate_stock_analyzer.quality.governance import (
    GovernanceConfig,
    GovernanceEvidence,
    analyze_governance,
)

CONFIG = GovernanceConfig.from_yaml(Path("config/quality/accounting_governance_v1.0.yml"))


def _evidence(metric: str, value: float | bool) -> GovernanceEvidence:
    return GovernanceEvidence(
        metric=metric,
        value=value,
        source="CVM_SYNTHETIC_FIXTURE",
        reference_date=date(2026, 8, 1),
    )


def test_governance_requires_coverage_and_rewards_stronger_controls() -> None:
    strong = analyze_governance([
        _evidence("board_independence_adequate", True),
        _evidence("audit_committee_present", True),
        _evidence("fiscal_council_present", True),
        _evidence("related_party_policy_present", True),
        _evidence("compensation_disclosure_adequate", True),
        _evidence("tag_along_adequate", True),
        _evidence("controller_voting_concentration", 0.35),
        _evidence("free_float", 0.45),
    ], config=CONFIG)
    weak = analyze_governance([
        _evidence("board_independence_adequate", False),
        _evidence("audit_committee_present", False),
        _evidence("fiscal_council_present", False),
        _evidence("related_party_policy_present", False),
        _evidence("compensation_disclosure_adequate", False),
        _evidence("tag_along_adequate", False),
        _evidence("controller_voting_concentration", 0.92),
        _evidence("free_float", 0.12),
    ], config=CONFIG)
    assert strong.rankable and weak.rankable
    assert strong.score > weak.score
    assert "HIGH_CONTROL_CONCENTRATION" in weak.flags
