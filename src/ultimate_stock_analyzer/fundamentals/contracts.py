from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FundamentalContract:
    name: str
    critical_inputs: tuple[str, ...]
    supporting_inputs: tuple[str, ...]
    excluded_business_models: tuple[str, ...] = ()


GENERAL_CORPORATE_CONTRACT = FundamentalContract(
    name="general_corporate_v1",
    critical_inputs=(
        "total_assets",
        "current_assets",
        "current_liabilities",
        "equity",
        "revenue",
        "gross_profit",
        "ebit",
        "pretax_income",
        "income_tax",
        "net_income_parent",
        "cash_from_operations",
    ),
    supporting_inputs=(
        "cash_and_equivalents",
        "financial_investments_current",
        "receivables_current",
        "inventories_current",
        "suppliers_current",
        "borrowings_current",
        "borrowings_noncurrent",
        "depreciation_and_amortization",
        "cost_of_goods_and_services",
        "noncurrent_liabilities",
        "cash_from_investing",
        "cash_from_financing",
    ),
    excluded_business_models=("bank", "insurer"),
)


BANK_PRUDENTIAL_CONTRACT = FundamentalContract(
    name="bank_prudential_ifdata_v1",
    critical_inputs=(
        "total_assets",
        "prior_total_assets",
        "equity",
        "prior_equity",
        "gross_credit_portfolio",
        "prior_gross_credit_portfolio",
        "annual_net_income",
        "annual_credit_loss_result",
        "basel_ratio",
        "tier1_ratio",
    ),
    supporting_inputs=(
        "core_equity_tier1_ratio",
        "leverage_ratio",
    ),
    excluded_business_models=(),
)


@dataclass(frozen=True, slots=True)
class ContractCoverage:
    contract: str
    critical_coverage: float
    total_coverage: float
    missing_critical: tuple[str, ...]
    missing_supporting: tuple[str, ...]


def evaluate_contract(
    values: dict[str, float],
    contract: FundamentalContract = GENERAL_CORPORATE_CONTRACT,
) -> ContractCoverage:
    missing_critical = tuple(
        name for name in contract.critical_inputs if name not in values
    )
    missing_supporting = tuple(
        name for name in contract.supporting_inputs if name not in values
    )
    critical_coverage = _coverage(len(contract.critical_inputs), len(missing_critical))
    all_inputs = contract.critical_inputs + contract.supporting_inputs
    total_missing = len(missing_critical) + len(missing_supporting)
    return ContractCoverage(
        contract=contract.name,
        critical_coverage=critical_coverage,
        total_coverage=_coverage(len(all_inputs), total_missing),
        missing_critical=missing_critical,
        missing_supporting=missing_supporting,
    )


def _coverage(total: int, missing: int) -> float:
    if total == 0:
        return 1.0
    return (total - missing) / total
