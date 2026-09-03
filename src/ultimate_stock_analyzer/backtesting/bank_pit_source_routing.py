from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ultimate_stock_analyzer.fundamentals.contracts import BANK_PRUDENTIAL_CONTRACT

SourceStatus = Literal[
    "validated_observed_pit",
    "timestamped_candidate_unaligned",
    "latest_state_non_pit",
    "unresolved",
    "outside_bank_accounting_pit_audit",
]

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
BANK_SCOPE_ALIGNMENT_UNPROVEN = "BANK_SCOPE_ALIGNMENT_UNPROVEN"
BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED = "BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED"
BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED = "BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED"
BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN = (
    "BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN"
)
BANK_MODEL_PIT_COVERAGE_INCOMPLETE = "BANK_MODEL_PIT_COVERAGE_INCOMPLETE"
CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)


@dataclass(frozen=True, slots=True)
class BankInputSourceRoute:
    input_name: str
    source: str
    status: SourceStatus
    evidence_field: str | None = None
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_name": self.input_name,
            "source": self.source,
            "status": self.status,
            "evidence_field": self.evidence_field,
            "blocker": self.blocker,
        }


@dataclass(frozen=True, slots=True)
class BankModelMetricRoute:
    metric: str
    category: str
    model_weight: float
    source: str
    status: SourceStatus
    dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "category": self.category,
            "model_weight": self.model_weight,
            "source": self.source,
            "status": self.status,
            "dependencies": list(self.dependencies),
        }


@dataclass(frozen=True, slots=True)
class CVMBankAccountingPeriodEvidence:
    fiscal_year: int
    total_assets: float
    equity: float
    net_income_consolidated: float
    total_assets_available_from: str
    equity_available_from: str
    net_income_available_from: str
    source_documents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fiscal_year": self.fiscal_year,
            "total_assets": self.total_assets,
            "equity": self.equity,
            "net_income_consolidated": self.net_income_consolidated,
            "total_assets_available_from": self.total_assets_available_from,
            "equity_available_from": self.equity_available_from,
            "net_income_available_from": self.net_income_available_from,
            "source_documents": list(self.source_documents),
        }


@dataclass(frozen=True, slots=True)
class BankPITSourceRoutingAudit:
    critical_routes: tuple[BankInputSourceRoute, ...]
    supporting_routes: tuple[BankInputSourceRoute, ...]
    model_metric_routes: tuple[BankModelMetricRoute, ...]
    cvm_accounting_periods: tuple[CVMBankAccountingPeriodEvidence, ...]
    blockers: tuple[str, ...]
    proven_pit_critical_coverage: float
    timestamped_candidate_or_better_critical_coverage: float
    proven_pit_model_weight: float
    timestamped_candidate_or_better_model_weight: float
    bank_evidence_point_in_time_ready: bool = False
    readiness_promotion_allowed: bool = False
    schema_version: str = "0.2"

    @property
    def effect(self) -> str:
        return "bank_hybrid_pit_source_routes_mapped_no_readiness_promotion"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "critical_routes": [item.to_dict() for item in self.critical_routes],
            "supporting_routes": [item.to_dict() for item in self.supporting_routes],
            "model_metric_routes": [item.to_dict() for item in self.model_metric_routes],
            "cvm_accounting_periods": [
                item.to_dict() for item in self.cvm_accounting_periods
            ],
            "blockers": list(self.blockers),
            "proven_pit_critical_coverage": self.proven_pit_critical_coverage,
            "timestamped_candidate_or_better_critical_coverage": (
                self.timestamped_candidate_or_better_critical_coverage
            ),
            "proven_pit_model_weight": self.proven_pit_model_weight,
            "timestamped_candidate_or_better_model_weight": (
                self.timestamped_candidate_or_better_model_weight
            ),
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def audit_bank_pit_source_routing(
    *,
    cvm_accounting_periods: tuple[CVMBankAccountingPeriodEvidence, ...] = (),
) -> BankPITSourceRoutingAudit:
    critical = _critical_routes()
    supporting = _supporting_routes()
    metrics = _model_metric_routes()

    expected_critical = set(BANK_PRUDENTIAL_CONTRACT.critical_inputs)
    routed_critical = {item.input_name for item in critical}
    if routed_critical != expected_critical:
        missing = sorted(expected_critical - routed_critical)
        extra = sorted(routed_critical - expected_critical)
        raise ValueError(f"bank critical route drift: missing={missing} extra={extra}")

    expected_supporting = set(BANK_PRUDENTIAL_CONTRACT.supporting_inputs)
    routed_supporting = {item.input_name for item in supporting}
    if routed_supporting != expected_supporting:
        missing = sorted(expected_supporting - routed_supporting)
        extra = sorted(routed_supporting - expected_supporting)
        raise ValueError(f"bank supporting route drift: missing={missing} extra={extra}")

    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        BANK_SCOPE_ALIGNMENT_UNPROVEN,
        BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
        BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
        BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN,
        BANK_MODEL_PIT_COVERAGE_INCOMPLETE,
        CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }
    proven = _route_coverage(critical, statuses={"validated_observed_pit"})
    candidate = _route_coverage(
        critical,
        statuses={"validated_observed_pit", "timestamped_candidate_unaligned"},
    )
    proven_weight = _metric_weight(metrics, statuses={"validated_observed_pit"})
    candidate_weight = _metric_weight(
        metrics,
        statuses={"validated_observed_pit", "timestamped_candidate_unaligned"},
    )
    return BankPITSourceRoutingAudit(
        critical_routes=critical,
        supporting_routes=supporting,
        model_metric_routes=metrics,
        cvm_accounting_periods=cvm_accounting_periods,
        blockers=tuple(sorted(blockers)),
        proven_pit_critical_coverage=proven,
        timestamped_candidate_or_better_critical_coverage=candidate,
        proven_pit_model_weight=proven_weight,
        timestamped_candidate_or_better_model_weight=candidate_weight,
    )


def _critical_routes() -> tuple[BankInputSourceRoute, ...]:
    cvm = "CVM_DFP_CONSOLIDATED"
    ifdata = "BCB_IFDATA_LATEST_STATE"
    pillar3 = "CVM_IPE_PILLAR3_KM1_OBSERVED_LEDGER"
    candidate: SourceStatus = "timestamped_candidate_unaligned"
    return (
        BankInputSourceRoute(
            "total_assets", cvm, candidate, "total_assets", BANK_SCOPE_ALIGNMENT_UNPROVEN
        ),
        BankInputSourceRoute(
            "prior_total_assets",
            cvm,
            candidate,
            "total_assets",
            BANK_SCOPE_ALIGNMENT_UNPROVEN,
        ),
        BankInputSourceRoute(
            "equity", cvm, candidate, "equity", BANK_SCOPE_ALIGNMENT_UNPROVEN
        ),
        BankInputSourceRoute(
            "prior_equity", cvm, candidate, "equity", BANK_SCOPE_ALIGNMENT_UNPROVEN
        ),
        BankInputSourceRoute(
            "gross_credit_portfolio",
            ifdata,
            "latest_state_non_pit",
            blocker=BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
        ),
        BankInputSourceRoute(
            "prior_gross_credit_portfolio",
            ifdata,
            "latest_state_non_pit",
            blocker=BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
        ),
        BankInputSourceRoute(
            "annual_net_income",
            cvm,
            candidate,
            "net_income_consolidated",
            BANK_SCOPE_ALIGNMENT_UNPROVEN,
        ),
        BankInputSourceRoute(
            "annual_credit_loss_result",
            ifdata,
            "latest_state_non_pit",
            blocker=BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
        ),
        BankInputSourceRoute(
            "basel_ratio", pillar3, "validated_observed_pit", "basel_ratio"
        ),
        BankInputSourceRoute(
            "tier1_ratio", pillar3, "validated_observed_pit", "tier1_ratio"
        ),
    )


def _supporting_routes() -> tuple[BankInputSourceRoute, ...]:
    pillar3 = "CVM_IPE_PILLAR3_KM1_OBSERVED_LEDGER"
    return (
        BankInputSourceRoute(
            "core_equity_tier1_ratio",
            pillar3,
            "validated_observed_pit",
            "core_equity_tier1_ratio",
        ),
        BankInputSourceRoute(
            "leverage_ratio",
            pillar3,
            "validated_observed_pit",
            "leverage_ratio",
        ),
    )


def _model_metric_routes() -> tuple[BankModelMetricRoute, ...]:
    cvm = "CVM_DFP_CONSOLIDATED_CANDIDATE"
    pillar3 = "CVM_IPE_PILLAR3_KM1_OBSERVED_LEDGER"
    ifdata = "BCB_IFDATA_LATEST_STATE"
    unresolved = "UNRESOLVED_OFFICIAL_PIT_SOURCE"
    dividends = "EXISTING_DIVIDEND_PIPELINE"
    return (
        BankModelMetricRoute(
            "roe",
            "profitability",
            0.1125,
            cvm,
            "timestamped_candidate_unaligned",
            ("annual_net_income", "equity", "prior_equity"),
        ),
        BankModelMetricRoute(
            "roa",
            "profitability",
            0.0625,
            cvm,
            "timestamped_candidate_unaligned",
            ("annual_net_income", "total_assets", "prior_total_assets"),
        ),
        BankModelMetricRoute(
            "net_interest_margin", "profitability", 0.075, unresolved, "unresolved"
        ),
        BankModelMetricRoute(
            "npl_90d_ratio", "asset_quality", 0.10, unresolved, "unresolved"
        ),
        BankModelMetricRoute(
            "cost_of_credit",
            "asset_quality",
            0.075,
            ifdata,
            "latest_state_non_pit",
            (
                "annual_credit_loss_result",
                "gross_credit_portfolio",
                "prior_gross_credit_portfolio",
            ),
        ),
        BankModelMetricRoute(
            "npl_coverage", "asset_quality", 0.075, unresolved, "unresolved"
        ),
        BankModelMetricRoute(
            "basel_ratio",
            "capital",
            0.09,
            pillar3,
            "validated_observed_pit",
            ("basel_ratio",),
        ),
        BankModelMetricRoute(
            "tier1_ratio",
            "capital",
            0.07,
            pillar3,
            "validated_observed_pit",
            ("tier1_ratio",),
        ),
        BankModelMetricRoute(
            "equity_to_assets",
            "capital",
            0.04,
            cvm,
            "timestamped_candidate_unaligned",
            ("equity", "total_assets"),
        ),
        BankModelMetricRoute(
            "efficiency_ratio", "efficiency", 0.105, ifdata, "latest_state_non_pit"
        ),
        BankModelMetricRoute(
            "fee_income_share", "efficiency", 0.045, ifdata, "latest_state_non_pit"
        ),
        BankModelMetricRoute(
            "loan_cagr_5y",
            "growth",
            0.02,
            ifdata,
            "latest_state_non_pit",
            ("gross_credit_portfolio",),
        ),
        BankModelMetricRoute(
            "net_income_cagr_5y",
            "growth",
            0.03,
            "CVM_DFP_CONSOLIDATED_CANDIDATE_REQUIRES_SIX_YEARS",
            "unresolved",
            ("annual_net_income",),
        ),
        BankModelMetricRoute(
            "dividend_regularity",
            "dividends",
            0.045,
            dividends,
            "outside_bank_accounting_pit_audit",
        ),
        BankModelMetricRoute(
            "dividend_sustainability",
            "dividends",
            0.04,
            dividends,
            "outside_bank_accounting_pit_audit",
        ),
        BankModelMetricRoute(
            "dividend_cagr_5y",
            "dividends",
            0.015,
            dividends,
            "outside_bank_accounting_pit_audit",
        ),
    )


def _route_coverage(
    routes: tuple[BankInputSourceRoute, ...],
    *,
    statuses: set[SourceStatus],
) -> float:
    if not routes:
        return 1.0
    return sum(item.status in statuses for item in routes) / len(routes)


def _metric_weight(
    routes: tuple[BankModelMetricRoute, ...],
    *,
    statuses: set[SourceStatus],
) -> float:
    return sum(item.model_weight for item in routes if item.status in statuses)
