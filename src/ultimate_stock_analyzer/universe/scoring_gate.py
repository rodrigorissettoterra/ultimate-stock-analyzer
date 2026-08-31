from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityReport,
)


@dataclass(frozen=True, slots=True, order=True)
class ExcludedCurrentAnalysisRow:
    company_id: str
    ticker: str
    status: str
    reason: str
    evidence_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurrentAnalysisUniverseGateReport:
    analysis_rows: int
    eligible_rows: int
    excluded_rows: int
    status_counts: dict[str, int]
    exclusions: tuple[ExcludedCurrentAnalysisRow, ...]
    scope: str = "CURRENT_STATE_ONLY"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def partition_current_analysis_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    eligibility_report: BrazilianEquityEligibilityReport,
) -> tuple[list[dict[str, Any]], CurrentAnalysisUniverseGateReport]:
    """Fail-closed current-state universe gate to run before investment scoring.

    The gate is intentionally engine-agnostic. It filters by canonical CVM issuer
    identity before any cross-sectional normalization or score calculation can be
    influenced by an issuer outside the Brazilian-company universe.
    """

    decisions = {
        decision.company_id: decision for decision in eligibility_report.decisions
    }
    records = [dict(row) for row in rows]
    eligible: list[dict[str, Any]] = []
    exclusions: list[ExcludedCurrentAnalysisRow] = []
    counts: Counter[str] = Counter()

    for index, row in enumerate(records):
        company_id = _row_company_id(row, index=index)
        row["company_id"] = company_id
        decision = decisions.get(company_id)
        if decision is None:
            raise ValueError(
                "Current analysis row lacks a universe eligibility decision: "
                f"company_id={company_id}"
            )

        counts[decision.status] += 1
        if decision.eligible:
            eligible.append(row)
            continue

        exclusions.append(
            ExcludedCurrentAnalysisRow(
                company_id=company_id,
                ticker=str(row.get("ticker") or "").strip().upper(),
                status=decision.status,
                reason=decision.reason,
                evidence_sources=decision.evidence_sources,
            )
        )

    return eligible, CurrentAnalysisUniverseGateReport(
        analysis_rows=len(records),
        eligible_rows=len(eligible),
        excluded_rows=len(exclusions),
        status_counts=dict(sorted(counts.items())),
        exclusions=tuple(sorted(exclusions)),
    )


def _row_company_id(row: Mapping[str, Any], *, index: int) -> str:
    value = str(row.get("company_id") or "").strip().lower()
    if not value:
        raise ValueError(
            "Current analysis universe gate requires canonical company_id; "
            f"row_index={index}"
        )
    if not value.startswith("cvm:"):
        raise ValueError(
            "Current analysis universe gate requires company_id=cvm:<CD_CVM>; "
            f"row_index={index} value={value}"
        )
    code = value.split(":", 1)[1]
    if not code.isdigit():
        raise ValueError(
            "Current analysis universe gate requires numeric CD_CVM; "
            f"row_index={index} value={value}"
        )
    return f"cvm:{int(code)}"
