from pathlib import Path

from ultimate_stock_analyzer.quality.accounting import (
    AccountingInputs,
    AccountingQualityConfig,
    analyze_accounting_quality,
)

CONFIG = AccountingQualityConfig.from_yaml(Path("config/quality/accounting_governance_v1.0.yml"))


def test_cash_backed_company_scores_higher_than_weak_conversion_company() -> None:
    strong = analyze_accounting_quality(
        AccountingInputs(
            net_income=100.0,
            operating_cash_flow=115.0,
            free_cash_flow=95.0,
            total_assets_begin=900.0,
            total_assets_end=1000.0,
            revenue=1200.0,
            receivables_begin=100.0,
            receivables_end=105.0,
            inventories_begin=80.0,
            inventories_end=82.0,
            nonrecurring_income=3.0,
        ),
        config=CONFIG,
    )
    weak = analyze_accounting_quality(
        AccountingInputs(
            net_income=100.0,
            operating_cash_flow=35.0,
            free_cash_flow=10.0,
            total_assets_begin=900.0,
            total_assets_end=1000.0,
            revenue=1200.0,
            receivables_begin=100.0,
            receivables_end=260.0,
            inventories_begin=80.0,
            inventories_end=220.0,
            nonrecurring_income=45.0,
        ),
        config=CONFIG,
    )
    assert strong.rankable and weak.rankable
    assert strong.score > weak.score
    assert "WEAK_CASH_CONVERSION" in weak.flags
    assert "HIGH_NONRECURRING_INCOME" in weak.flags
