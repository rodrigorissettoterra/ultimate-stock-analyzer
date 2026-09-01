from __future__ import annotations

import json
from pathlib import Path

from ultimate_stock_analyzer.scoring.fige_metric_selection import (
    FigeMetricSelectionContract,
    evaluate_fige_metric_selection,
)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate the FIGE non-prudential metric-selection contract."
    )
    parser.add_argument("--audit", required=True)
    parser.add_argument(
        "--contract",
        default=(
            "config/scoring/"
            "fige_financial_non_prudential_metric_contract_v0.1.yml"
        ),
    )
    parser.add_argument("--output", default="fige-metric-selection-evidence.json")
    args = parser.parse_args()

    audit_payload = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    contract = FigeMetricSelectionContract.from_yaml(args.contract)
    report = evaluate_fige_metric_selection(audit_payload, contract)

    primary = tuple(
        metric
        for metric in report.metrics
        if metric.role == "PRIMARY_MODEL_CANDIDATE_UNCALIBRATED"
    )
    if not primary:
        raise RuntimeError("FIGE metric-selection contract has no primary candidates")
    saturated_primary = tuple(
        metric.name for metric in primary if metric.empirically_saturated
    )
    if saturated_primary:
        raise RuntimeError(
            "FIGE primary metric candidates are empirically saturated: "
            + ", ".join(saturated_primary)
        )
    if report.score_ready or report.routing_ready or report.registry_resolvable:
        raise RuntimeError("FIGE metric-selection block must not activate scoring/routing")
    if report.scoring_status != "BLOCKED_INSUFFICIENT_COMPARABLE_PEERS":
        raise RuntimeError(
            "FIGE metric-selection scoring gate changed unexpectedly: "
            + report.scoring_status
        )

    Path(args.output).write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
