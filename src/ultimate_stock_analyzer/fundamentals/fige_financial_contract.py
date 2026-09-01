from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.fundamentals.contracts import (
    ContractCoverage,
    FundamentalContract,
    evaluate_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

FIGE_COMPANY_ID = "cvm:6041"


@dataclass(frozen=True, slots=True)
class FigeFinancialAccountBinding:
    concept_id: str
    statement: str
    account_code: str
    expected_label: str


FIGE_FINANCIAL_ACCOUNT_BINDINGS = (
    FigeFinancialAccountBinding("total_assets", "BPA", "1", "Ativo Total"),
    FigeFinancialAccountBinding(
        "cash_and_equivalents",
        "BPA",
        "1.01",
        "Caixa e Equivalentes de Caixa",
    ),
    FigeFinancialAccountBinding(
        "financial_assets",
        "BPA",
        "1.02",
        "Ativos Financeiros",
    ),
    FigeFinancialAccountBinding(
        "securities_amortized_cost",
        "BPA",
        "1.02.04.03",
        "Títulos e Valores Mobiliários",
    ),
    FigeFinancialAccountBinding(
        "financial_liabilities_amortized_cost",
        "BPP",
        "2.02",
        "Passivos Financeiros ao Custo Amortizado",
    ),
    FigeFinancialAccountBinding("provisions", "BPP", "2.03", "Provisões"),
    FigeFinancialAccountBinding(
        "fiscal_liabilities",
        "BPP",
        "2.04",
        "Passivos Fiscais",
    ),
    FigeFinancialAccountBinding("equity", "BPP", "2.07", "Patrimônio Líquido"),
    FigeFinancialAccountBinding(
        "financial_intermediation_revenue",
        "DRE",
        "3.01",
        "Receitas de Intermediação Financeira",
    ),
    FigeFinancialAccountBinding(
        "financial_intermediation_expense",
        "DRE",
        "3.02",
        "Despesas de Intermediação Financeira",
    ),
    FigeFinancialAccountBinding(
        "gross_financial_intermediation_result",
        "DRE",
        "3.03",
        "Resultado Bruto de Intermediação Financeira",
    ),
    FigeFinancialAccountBinding(
        "other_operating_result",
        "DRE",
        "3.04",
        "Outras Despesas e Receitas Operacionais",
    ),
    FigeFinancialAccountBinding(
        "pretax_income",
        "DRE",
        "3.05",
        "Resultado antes dos Tributos sobre o Lucro",
    ),
    FigeFinancialAccountBinding(
        "income_tax",
        "DRE",
        "3.06",
        "Imposto de Renda e Contribuição Social sobre o Lucro",
    ),
    FigeFinancialAccountBinding(
        "continuing_operations_income",
        "DRE",
        "3.07",
        "Lucro ou Prejuízo das Operações Continuadas",
    ),
    FigeFinancialAccountBinding(
        "net_income",
        "DRE",
        "3.11",
        "Lucro ou Prejuízo Líquido do Período",
    ),
)

FIGE_FINANCIAL_CVM_CONTRACT = FundamentalContract(
    name="fige_financial_cvm_v1",
    critical_inputs=(
        "total_assets",
        "cash_and_equivalents",
        "financial_assets",
        "equity",
        "financial_intermediation_revenue",
        "financial_intermediation_expense",
        "gross_financial_intermediation_result",
        "pretax_income",
        "income_tax",
        "net_income",
    ),
    supporting_inputs=(
        "securities_amortized_cost",
        "financial_liabilities_amortized_cost",
        "provisions",
        "fiscal_liabilities",
        "other_operating_result",
        "continuing_operations_income",
    ),
)


@dataclass(frozen=True, slots=True)
class FigeFinancialContractEvaluation:
    company_id: str
    reference_date: date | None
    values: dict[str, float]
    coverage: ContractCoverage
    scope: str = "FIGE_CVM_FINANCIAL_ACCOUNTING_CONTRACT"
    effect: str = "contract_defined_not_routed"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_fige_financial_contract(
    report: FinancialStatementTreeAuditReport,
) -> FigeFinancialContractEvaluation:
    values = extract_fige_financial_values(report)
    return FigeFinancialContractEvaluation(
        company_id=report.company_id,
        reference_date=report.reference_date,
        values=values,
        coverage=evaluate_contract(values, FIGE_FINANCIAL_CVM_CONTRACT),
    )


def extract_fige_financial_values(
    report: FinancialStatementTreeAuditReport,
) -> dict[str, float]:
    if report.company_id != FIGE_COMPANY_ID:
        raise ValueError(
            "FIGE financial contract company identity mismatch: "
            f"expected={FIGE_COMPANY_ID} actual={report.company_id}"
        )

    values: dict[str, float] = {}
    for binding in FIGE_FINANCIAL_ACCOUNT_BINDINGS:
        matching = [
            line
            for line in report.lines
            if line.statement == binding.statement
            and line.account_code == binding.account_code
        ]
        if len(matching) > 1:
            raise ValueError(
                "ambiguous FIGE financial account after tree normalization: "
                f"statement={binding.statement} account_code={binding.account_code}"
            )
        if not matching:
            continue
        line = matching[0]
        actual_label = _normalize_label(line.account_name)
        expected_label = _normalize_label(binding.expected_label)
        if actual_label != expected_label:
            raise ValueError(
                "FIGE financial account label mismatch: "
                f"statement={binding.statement} account_code={binding.account_code} "
                f"expected={binding.expected_label!r} actual={line.account_name!r}"
            )
        values[binding.concept_id] = float(line.value_brl)
    return values


def _normalize_label(value: str) -> str:
    return " ".join(value.split())
