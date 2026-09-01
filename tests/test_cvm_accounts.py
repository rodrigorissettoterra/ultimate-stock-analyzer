from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.fundamentals.contracts import evaluate_contract
from ultimate_stock_analyzer.fundamentals.cvm_accounts import extract_fixed_accounts


def _line(
    statement: str,
    code: str,
    value: float,
    *,
    scope: str = "DF Consolidado",
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id="cvm:123",
        cvm_code=123,
        company_name="TESTE S.A.",
        document_type="DFP",
        statement=statement,
        consolidation_scope=scope,
        reference_date=date(2025, 12, 31),
        fiscal_order="ÚLTIMO",
        account_code=code,
        account_name=code,
        value_brl=value,
        version=1,
        document_id=10,
        available_from=datetime(2026, 2, 20, tzinfo=UTC),
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
    )


def test_exact_cvm_account_extraction_keeps_lineage() -> None:
    lines = [
        _line("BPA", "1", 1000),
        _line("BPA", "1.01", 400),
        _line("BPP", "2.01", 250),
        _line("BPP", "2.03", 500),
        _line("DRE", "3.01", 800),
        _line("DRE", "3.03", 300),
        _line("DRE", "3.05", 150),
        _line("DRE", "3.07", 130),
        _line("DRE", "3.08", -30),
        _line("DRE", "3.11.01", 100),
        _line("DFC_MD", "6.01", 140),
    ]

    extraction = extract_fixed_accounts(
        lines,
        company_id="cvm:123",
        reference_date=date(2025, 12, 31),
        consolidation_scope="DF Consolidado",
    )
    coverage = evaluate_contract(extraction.values)

    assert extraction.values["revenue"] == 800
    assert extraction.lines["revenue"].account_code == "3.01"
    assert coverage.critical_coverage > 0.8
    assert "cost_of_goods_and_services" in coverage.missing_supporting


def test_default_scope_prefers_consolidated_and_never_fills_from_individual() -> None:
    lines = [
        _line("BPA", "1", 500, scope="DF Individual"),
        _line("BPP", "2.03", 100, scope="DF Individual"),
        _line("DRE", "3.01", 10, scope="DF Individual"),
        _line("DRE", "3.11.01", 50, scope="DF Individual"),
        _line("BPA", "1", 2000, scope="DF Consolidado"),
        _line("BPP", "2.03", 800, scope="DF Consolidado"),
        _line("DRE", "3.01", 1000, scope="DF Consolidado"),
    ]

    extraction = extract_fixed_accounts(
        lines,
        company_id="cvm:123",
        reference_date=date(2025, 12, 31),
    )

    assert extraction.values["total_assets"] == 2000
    assert extraction.values["equity"] == 800
    assert extraction.values["revenue"] == 1000
    assert "net_income_parent" in extraction.missing
    assert {
        line.consolidation_scope for line in extraction.lines.values()
    } == {"DF Consolidado"}


def test_default_scope_uses_individual_only_when_consolidated_is_absent() -> None:
    lines = [
        _line("BPA", "1", 500, scope="DF Individual"),
        _line("BPP", "2.03", 100, scope="DF Individual"),
        _line("DRE", "3.01", 10, scope="DF Individual"),
    ]

    extraction = extract_fixed_accounts(
        lines,
        company_id="cvm:123",
        reference_date=date(2025, 12, 31),
    )

    assert extraction.values["total_assets"] == 500
    assert extraction.values["equity"] == 100
    assert extraction.values["revenue"] == 10
    assert {
        line.consolidation_scope for line in extraction.lines.values()
    } == {"DF Individual"}


def test_explicit_individual_scope_overrides_default_consolidated_preference() -> None:
    lines = [
        _line("BPA", "1", 500, scope="DF Individual"),
        _line("BPA", "1", 2000, scope="DF Consolidado"),
    ]

    extraction = extract_fixed_accounts(
        lines,
        company_id="cvm:123",
        reference_date=date(2025, 12, 31),
        consolidation_scope="DF Individual",
    )

    assert extraction.values["total_assets"] == 500
    assert extraction.lines["total_assets"].consolidation_scope == "DF Individual"
