from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from ultimate_stock_analyzer.universe.current_equity_securities import (
    CurrentBrazilianEquitySecurityUniverseReport,
)
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
    security_universe_report: CurrentBrazilianEquitySecurityUniverseReport | None = None,
) -> tuple[list[dict[str, Any]], CurrentAnalysisUniverseGateReport]:
    """Fail-closed current-state universe gate to run before investment scoring.

    Canonical CVM issuer identity is always required. When ``security_universe_report``
    is supplied, the gate additionally requires an exact B3 security code in ``ticker``
    and only passes rows whose canonical company/security pair is eligible in the
    current Brazilian core-equity universe.

    The security-level path is intentionally current-state only. Neither the CVM
    jurisdiction registry nor the current B3 instrument/trading evidence is
    point-in-time eligible for historical backtests.
    """

    decisions = {
        decision.company_id: decision for decision in eligibility_report.decisions
    }
    records = [dict(row) for row in rows]
    eligible: list[dict[str, Any]] = []
    exclusions: list[ExcludedCurrentAnalysisRow] = []
    counts: Counter[str] = Counter()

    security_company_decisions = None
    security_decisions = None
    if security_universe_report is not None:
        security_company_decisions = {
            decision.company_id: decision
            for decision in security_universe_report.company_decisions
        }
        security_decisions = {
            (decision.company_id, decision.code): decision
            for decision in security_universe_report.security_decisions
        }
        if len(security_company_decisions) != len(
            security_universe_report.company_decisions
        ):
            raise ValueError("Current security universe contains duplicate company_id values")
        if len(security_decisions) != len(security_universe_report.security_decisions):
            raise ValueError(
                "Current security universe contains duplicate company/security decisions"
            )

    for index, row in enumerate(records):
        company_id = _row_company_id(row, index=index)
        row["company_id"] = company_id
        decision = decisions.get(company_id)
        if decision is None:
            raise ValueError(
                "Current analysis row lacks a universe eligibility decision: "
                f"company_id={company_id}"
            )

        if not decision.eligible:
            counts[decision.status] += 1
            exclusions.append(
                ExcludedCurrentAnalysisRow(
                    company_id=company_id,
                    ticker=_normalized_ticker(row),
                    status=decision.status,
                    reason=decision.reason,
                    evidence_sources=decision.evidence_sources,
                )
            )
            continue

        if security_universe_report is None:
            counts[decision.status] += 1
            eligible.append(row)
            continue

        ticker = _row_ticker(row, index=index)
        row["ticker"] = ticker
        assert security_company_decisions is not None
        assert security_decisions is not None

        company_security_decision = security_company_decisions.get(company_id)
        if company_security_decision is None:
            raise ValueError(
                "Current analysis row lacks a current security-universe company decision: "
                f"company_id={company_id}"
            )
        if not company_security_decision.eligible:
            counts[company_security_decision.status] += 1
            exclusions.append(
                ExcludedCurrentAnalysisRow(
                    company_id=company_id,
                    ticker=ticker,
                    status=company_security_decision.status,
                    reason=company_security_decision.reason,
                    evidence_sources=("B3 GetDetail", "B3 COTAHIST"),
                )
            )
            continue

        security_decision = security_decisions.get((company_id, ticker))
        if security_decision is None:
            status = "EXCLUDED_SECURITY_NOT_IN_CURRENT_UNIVERSE"
            counts[status] += 1
            exclusions.append(
                ExcludedCurrentAnalysisRow(
                    company_id=company_id,
                    ticker=ticker,
                    status=status,
                    reason=(
                        "The exact ticker has no current security-universe decision for "
                        "this canonical CVM company identity."
                    ),
                    evidence_sources=("B3 GetDetail", "B3 COTAHIST"),
                )
            )
            continue
        if not security_decision.eligible:
            counts[security_decision.status] += 1
            exclusions.append(
                ExcludedCurrentAnalysisRow(
                    company_id=company_id,
                    ticker=ticker,
                    status=security_decision.status,
                    reason=security_decision.reason,
                    evidence_sources=("B3 GetDetail", "B3 COTAHIST"),
                )
            )
            continue

        counts[security_decision.status] += 1
        eligible.append(row)

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


def _row_ticker(row: Mapping[str, Any], *, index: int) -> str:
    ticker = _normalized_ticker(row)
    if not ticker:
        raise ValueError(
            "Current analysis security gate requires exact B3 security code in ticker; "
            f"row_index={index}"
        )
    return ticker


def _normalized_ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").strip().upper()
