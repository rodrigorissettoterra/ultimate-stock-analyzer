from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.fundamentals.contracts import (
    ContractCoverage,
    FundamentalContract,
    evaluate_contract,
)
from ultimate_stock_analyzer.fundamentals.metrics import safe_div
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

ITSA_COMPANY_ID = "cvm:7617"
ITSA_CVM_CODE = 7617


@dataclass(frozen=True, slots=True)
class ItsaHoldingAccountBinding:
    concept_id: str
    statement: str
    account_code: str
    expected_label: str


ITSA_HOLDING_ACCOUNT_BINDINGS = (
    ItsaHoldingAccountBinding("total_assets", "BPA", "1", "Ativo Total"),
    ItsaHoldingAccountBinding(
        "investments_total",
        "BPA",
        "1.02.02",
        "Investimentos",
    ),
    ItsaHoldingAccountBinding(
        "equity_investments",
        "BPA",
        "1.02.02.01",
        "Participações Societárias",
    ),
    ItsaHoldingAccountBinding(
        "other_investments",
        "BPA",
        "1.02.02.01.04",
        "Outros Investimentos",
    ),
    ItsaHoldingAccountBinding(
        "equity",
        "BPP",
        "2.03",
        "Patrimônio Líquido",
    ),
    ItsaHoldingAccountBinding(
        "equity_method_result",
        "DRE",
        "3.04.06",
        "Resultado de Equivalência Patrimonial",
    ),
    ItsaHoldingAccountBinding(
        "net_income_parent",
        "DRE",
        "3.11",
        "Lucro/Prejuízo do Período",
    ),
)

ITSA_HOLDING_CVM_CONTRACT = FundamentalContract(
    name="itsa_holding_cvm_v1",
    critical_inputs=(
        "total_assets",
        "investments_total",
        "equity",
        "equity_method_result",
        "net_income_parent",
    ),
    supporting_inputs=(
        "equity_investments",
        "other_investments",
    ),
)


@dataclass(frozen=True, slots=True)
class ItsaHoldingContractEvaluation:
    company_id: str
    reference_date: date | None
    values: dict[str, float]
    descriptive_metrics: dict[str, float | None]
    coverage: ContractCoverage
    scope: str = "ITSA_HOLDING_CVM_ACCOUNTING_CONTRACT"
    effect: str = "contract_defined_not_routed"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_itsa_holding_contract(
    report: FinancialStatementTreeAuditReport,
) -> ItsaHoldingContractEvaluation:
    values = extract_itsa_holding_values(report)
    return ItsaHoldingContractEvaluation(
        company_id=report.company_id,
        reference_date=report.reference_date,
        values=values,
        descriptive_metrics=_descriptive_metrics(values),
        coverage=evaluate_contract(values, ITSA_HOLDING_CVM_CONTRACT),
    )


def extract_itsa_holding_values(
    report: FinancialStatementTreeAuditReport,
) -> dict[str, float]:
    if report.company_id != ITSA_COMPANY_ID:
        raise ValueError(
            "ITSA holding contract company identity mismatch: "
            f"expected={ITSA_COMPANY_ID} actual={report.company_id}"
        )

    values: dict[str, float] = {}
    for binding in ITSA_HOLDING_ACCOUNT_BINDINGS:
        matching = [
            line
            for line in report.lines
            if line.statement == binding.statement
            and line.account_code == binding.account_code
        ]
        if len(matching) > 1:
            raise ValueError(
                "ambiguous ITSA holding account after tree normalization: "
                f"statement={binding.statement} account_code={binding.account_code}"
            )
        if not matching:
            continue
        line = matching[0]
        if _normalize_label(line.account_name) != _normalize_label(
            binding.expected_label
        ):
            raise ValueError(
                "ITSA holding account label mismatch: "
                f"statement={binding.statement} account_code={binding.account_code} "
                f"expected={binding.expected_label!r} actual={line.account_name!r}"
            )
        values[binding.concept_id] = float(line.value_brl)
    return values


def _descriptive_metrics(
    values: dict[str, float],
) -> dict[str, float | None]:
    investments = values.get("investments_total")
    total_assets = values.get("total_assets")
    equity = values.get("equity")
    equity_method_result = values.get("equity_method_result")
    net_income = values.get("net_income_parent")
    equity_investments = values.get("equity_investments")
    other_investments = values.get("other_investments")

    return {
        "investments_to_assets": safe_div(investments, total_assets),
        "equity_to_assets": safe_div(equity, total_assets),
        "equity_method_to_net_income": safe_div(
            equity_method_result,
            net_income,
        ),
        "equity_investments_to_investments": safe_div(
            equity_investments,
            investments,
        ),
        "other_investments_to_investments": safe_div(
            other_investments,
            investments,
        ),
    }


def _normalize_label(value: str) -> str:
    return " ".join(value.split())
