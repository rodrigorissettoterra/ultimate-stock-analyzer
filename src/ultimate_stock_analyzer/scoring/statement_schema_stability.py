from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

STATUS_STABLE_EXACT = "STABLE_EXACT_LABEL"
STATUS_LABEL_CHANGED = "LABEL_CHANGED_REVIEW"
STATUS_MISSING = "MISSING_PERIOD"
STATUS_MISSING_AND_CHANGED = "MISSING_AND_LABEL_CHANGED_REVIEW"


@dataclass(frozen=True, slots=True)
class StatementSchemaCandidate:
    concept_id: str
    statement: str
    account_code: str
    baseline_label: str
    tier: str = "supporting"


@dataclass(frozen=True, slots=True)
class StatementSchemaObservation:
    fiscal_year: int
    reference_date: date | None
    account_name: str | None
    value_brl: float | None
    version: int | None
    document_id: int | None

    @property
    def present(self) -> bool:
        return self.account_name is not None


@dataclass(frozen=True, slots=True)
class StatementSchemaCandidateResult:
    concept_id: str
    statement: str
    account_code: str
    baseline_label: str
    tier: str
    status: str
    missing_years: tuple[int, ...]
    distinct_labels: tuple[str, ...]
    observations: tuple[StatementSchemaObservation, ...]


@dataclass(frozen=True, slots=True)
class StatementSchemaStabilityReport:
    company_id: str
    start_year: int
    end_year: int
    candidate_count: int
    status_counts: dict[str, int]
    results: tuple[StatementSchemaCandidateResult, ...]
    scope: str = "DIAGNOSTIC_CVM_STATEMENT_SCHEMA_STABILITY"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_statement_schema_stability(
    reports_by_year: dict[int, FinancialStatementTreeAuditReport],
    *,
    company_id: str,
    candidates: tuple[StatementSchemaCandidate, ...],
    start_year: int,
    end_year: int,
) -> StatementSchemaStabilityReport:
    """Compare exact CVM statement/account codes across annual DFP snapshots.

    The audit deliberately does not infer semantic equivalence from account names.
    A label change on the same exact code is surfaced for review, and an absent code
    remains missing/UNKNOWN.
    """

    if start_year > end_year:
        raise ValueError("start_year must not be greater than end_year")
    if not candidates:
        raise ValueError("at least one schema candidate is required")

    years = tuple(range(start_year, end_year + 1))
    results: list[StatementSchemaCandidateResult] = []

    for candidate in candidates:
        observations: list[StatementSchemaObservation] = []
        for year in years:
            report = reports_by_year.get(year)
            if report is None:
                observations.append(
                    StatementSchemaObservation(
                        fiscal_year=year,
                        reference_date=None,
                        account_name=None,
                        value_brl=None,
                        version=None,
                        document_id=None,
                    )
                )
                continue
            if report.company_id != company_id:
                raise ValueError(
                    "statement-schema report company identity mismatch: "
                    f"expected={company_id} actual={report.company_id} year={year}"
                )
            matching = [
                line
                for line in report.lines
                if line.statement == candidate.statement
                and line.account_code == candidate.account_code
            ]
            if len(matching) > 1:
                raise ValueError(
                    "ambiguous statement-schema candidate after tree normalization: "
                    f"year={year} statement={candidate.statement} "
                    f"account_code={candidate.account_code} matches={len(matching)}"
                )
            if not matching:
                observations.append(
                    StatementSchemaObservation(
                        fiscal_year=year,
                        reference_date=report.reference_date,
                        account_name=None,
                        value_brl=None,
                        version=None,
                        document_id=None,
                    )
                )
                continue
            line = matching[0]
            observations.append(
                StatementSchemaObservation(
                    fiscal_year=year,
                    reference_date=report.reference_date,
                    account_name=line.account_name,
                    value_brl=line.value_brl,
                    version=line.version,
                    document_id=line.document_id,
                )
            )

        missing_years = tuple(
            row.fiscal_year for row in observations if not row.present
        )
        labels = tuple(
            sorted(
                {
                    _normalize_label(row.account_name)
                    for row in observations
                    if row.account_name is not None
                }
            )
        )
        baseline = _normalize_label(candidate.baseline_label)
        label_changed = any(label != baseline for label in labels)

        if missing_years and label_changed:
            status = STATUS_MISSING_AND_CHANGED
        elif missing_years:
            status = STATUS_MISSING
        elif label_changed:
            status = STATUS_LABEL_CHANGED
        else:
            status = STATUS_STABLE_EXACT

        results.append(
            StatementSchemaCandidateResult(
                concept_id=candidate.concept_id,
                statement=candidate.statement,
                account_code=candidate.account_code,
                baseline_label=candidate.baseline_label,
                tier=candidate.tier,
                status=status,
                missing_years=missing_years,
                distinct_labels=labels,
                observations=tuple(observations),
            )
        )

    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    return StatementSchemaStabilityReport(
        company_id=company_id,
        start_year=start_year,
        end_year=end_year,
        candidate_count=len(candidates),
        status_counts=dict(sorted(status_counts.items())),
        results=tuple(results),
    )


def _normalize_label(value: str | None) -> str:
    return " ".join(str(value or "").split())
