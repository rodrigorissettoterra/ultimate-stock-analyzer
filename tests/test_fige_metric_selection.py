from __future__ import annotations

from pathlib import Path

import pytest

from ultimate_stock_analyzer.scoring.fige_metric_selection import (
    FigeMetricSelectionContract,
    evaluate_fige_metric_selection,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "config/scoring/fige_financial_non_prudential_metric_contract_v0.1.yml"
)


def _annual(year: int, *, expense_ratio: float = 0.0) -> dict[str, object]:
    offset = year - 2021
    return {
        "company_id": "cvm:6041",
        "fiscal_year": year,
        "reference_date": f"{year}-12-31",
        "values": {"net_income": 10.0 + offset},
        "metrics": {
            "roe_closing_equity": 0.05 + offset * 0.005,
            "roe_average_equity": None if year == 2021 else 0.052 + offset * 0.004,
            "roa_closing_assets": 0.045 + offset * 0.004,
            "roa_average_assets": None if year == 2021 else 0.047 + offset * 0.003,
            "net_income_to_closing_financial_assets": 0.046 + offset * 0.004,
            "net_income_to_average_financial_assets": (
                None if year == 2021 else 0.048 + offset * 0.003
            ),
            "financial_assets_to_assets": 0.98 + offset * 0.001,
            "securities_to_assets": 0.95 + offset * 0.001,
            "securities_to_financial_assets": 0.97 + offset * 0.001,
            "equity_to_assets": 0.96 + offset * 0.002,
            "financial_liabilities_to_assets": 0.001 * offset,
            "fiscal_liabilities_to_assets": 0.01 + offset * 0.002,
            "gross_intermediation_result_to_closing_assets": 0.06 + offset * 0.003,
            "gross_intermediation_result_to_average_assets": (
                None if year == 2021 else 0.061 + offset * 0.002
            ),
            "intermediation_expense_to_revenue": expense_ratio,
            "other_operating_result_to_gross_intermediation_result": (
                -0.10 + offset * 0.01
            ),
            "pretax_income_to_gross_intermediation_result": 0.88 + offset * 0.01,
            "effective_tax_burden": 0.19 - offset * 0.002,
            "net_income_to_pretax_income": 0.81 + offset * 0.002,
            "non_continuing_result_gap_to_abs_net_income": 0.0,
            "roe_denominator_sensitivity": (
                None if year == 2021 else 0.01 / offset
            ),
            "roa_denominator_sensitivity": (
                None if year == 2021 else 0.008 / offset
            ),
            "financial_asset_return_denominator_sensitivity": (
                None if year == 2021 else 0.009 / offset
            ),
        },
        "warnings": [],
    }


def _audit_payload() -> dict[str, object]:
    annual = [_annual(year) for year in range(2021, 2026)]
    return {
        "company_id": "cvm:6041",
        "effect": "diagnostic_only_not_routed_or_scored",
        "point_in_time_eligible": False,
        "economic_audit": {
            "annual_audits": annual,
            "historical_statistics": {
                "positive_net_income_year_ratio": 1.0,
                "net_income_coefficient_of_variation": 0.20,
                "roa_closing_assets_population_stdev": 0.006,
            },
        },
    }


def test_current_fige_metric_selection_contract_is_diagnostic_only() -> None:
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)

    assert contract.company_id == "cvm:6041"
    assert contract.effect == "diagnostic_only_no_scoring"
    assert contract.required_years == (2021, 2022, 2023, 2024, 2025)
    assert contract.current_exact_company_ids == ("cvm:6041",)
    assert contract.min_comparable_peers_for_cross_sectional_score == 8


def test_selection_keeps_scoring_and_routing_blocked_with_one_peer() -> None:
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)
    report = evaluate_fige_metric_selection(_audit_payload(), contract)

    assert report.scoring_status == "BLOCKED_INSUFFICIENT_COMPARABLE_PEERS"
    assert report.score_ready is False
    assert report.routing_ready is False
    assert report.registry_resolvable is False

    roles = {metric.name: metric.role for metric in report.metrics}
    assert roles["roa_closing_assets"] == "PRIMARY_MODEL_CANDIDATE_UNCALIBRATED"
    assert roles["roe_closing_equity"] == "SECONDARY_MODEL_CANDIDATE_UNCALIBRATED"
    assert roles["financial_assets_to_assets"] == "GUARDRAIL"
    assert roles["intermediation_expense_to_revenue"] == "DIAGNOSTIC_ONLY"

    blocked = {concept.name for concept in report.blocked_concepts}
    assert blocked == {"balance_growth_quality", "dividend_sustainability"}


def test_selection_detects_saturated_metrics_without_promoting_them() -> None:
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)
    report = evaluate_fige_metric_selection(_audit_payload(), contract)
    evidence = {metric.name: metric for metric in report.metrics}

    assert evidence["intermediation_expense_to_revenue"].empirically_saturated is True
    assert evidence["non_continuing_result_gap_to_abs_net_income"].empirically_saturated is True
    assert evidence["roa_closing_assets"].empirically_saturated is False
    assert any(
        warning.startswith("EMPIRICALLY_SATURATED_METRICS:")
        for warning in report.warnings
    )


def test_selection_preserves_first_year_unknown_for_average_denominators() -> None:
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)
    report = evaluate_fige_metric_selection(_audit_payload(), contract)
    evidence = {metric.name: metric for metric in report.metrics}

    assert evidence["roa_average_assets"].available_observations == 4
    assert evidence["roe_average_equity"].available_observations == 4
    assert evidence["roa_closing_assets"].available_observations == 5


def test_selection_fails_closed_on_missing_required_metric_evidence() -> None:
    payload = _audit_payload()
    annual = payload["economic_audit"]["annual_audits"]  # type: ignore[index]
    annual[0]["metrics"]["roa_closing_assets"] = None  # type: ignore[index]
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)

    with pytest.raises(ValueError, match="insufficient evidence"):
        evaluate_fige_metric_selection(payload, contract)


def test_selection_fails_closed_on_wrong_company_or_year_window() -> None:
    contract = FigeMetricSelectionContract.from_yaml(CONTRACT_PATH)
    payload = _audit_payload()
    payload["company_id"] = "cvm:9999"
    with pytest.raises(ValueError, match="identity mismatch"):
        evaluate_fige_metric_selection(payload, contract)

    payload = _audit_payload()
    payload["economic_audit"]["annual_audits"] = payload["economic_audit"][  # type: ignore[index]
        "annual_audits"
    ][1:]  # type: ignore[index]
    with pytest.raises(ValueError, match="years mismatch"):
        evaluate_fige_metric_selection(payload, contract)


def test_contract_rejects_scoring_configuration(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text(
        """
version: "0.1.0"
contract_id: bad
company_id: cvm:6041
effect: diagnostic_only_no_scoring
required_years: [2021, 2022]
peer_policy:
  current_exact_company_ids: [cvm:6041]
  min_comparable_peers_for_cross_sectional_score: 8
metrics:
  - name: roa_closing_assets
    source: annual_metric
    role: PRIMARY_MODEL_CANDIDATE_UNCALIBRATED
    required_observations: 2
    weight: 1.0
    rationale: should fail
concepts:
  - name: dividend_sustainability
    role: BLOCKED_WITH_CURRENT_CONTRACT
    rationale: blocked
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot contain scoring configuration"):
        FigeMetricSelectionContract.from_yaml(path)
