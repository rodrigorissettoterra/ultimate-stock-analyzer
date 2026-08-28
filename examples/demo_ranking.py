from pathlib import Path

from ultimate_stock_analyzer.domain.models import RedFlag
from ultimate_stock_analyzer.orchestration.service import AnalyzerService

ROOT = Path(__file__).resolve().parents[1]
service = AnalyzerService(ROOT / "config/scoring/model_v0.1.yml")

# Synthetic values are deliberate: this example never claims to contain real market data.
rows = [
    {
        "ticker": "ALFA3", "company_name": "Synthetic Alfa", "sector": "Industrial",
        "current_price": 20.0, "dy_ttm": 0.072,
        "roe": 0.22, "roic": 0.19, "ebit_margin": 0.18, "net_margin": 0.12,
        "net_debt_ebitda": 0.8, "interest_coverage": 8.5, "current_ratio": 1.8, "debt_to_equity": 0.35,
        "cash_conversion": 1.10, "fcf_yield": 0.09, "fcf_margin": 0.10,
        "revenue_cagr_5y": 0.11, "eps_cagr_5y": 0.14, "fcf_cagr_5y": 0.12,
        "accrual_quality": 0.90, "piotroski_f": 8, "beneish_m": -2.4, "earnings_cash_consistency": 0.90,
        "dividend_regularity": 95, "dy_5y_median": 0.065, "dividend_cagr_5y": 0.08,
        "payout_sustainability": 90, "fcf_payout_sustainability": 88,
        "capital_allocation": 90, "governance": 88, "predictability": 92,
        "earnings_yield": 0.09, "fcf_yield_valuation": 0.09, "ev_ebit": 8.0, "pb": 1.6, "margin_of_safety": 0.18,
        "entry_value": 82, "distance_ma200_attractiveness": 70, "rsi_attractiveness": 68, "speculation_safety": 90,
        "news_score": 82, "rental_score": 58, "macro_score": 70, "liquidity_score": 88,
        "risk_score": 22, "short_pressure_score": 35, "entry_score": 78,
        "source_confidence": 0.98, "freshness_confidence": 0.97, "conflict_confidence": 0.99,
        "lending_rate_annual": 0.03, "lending_utilization": 0.04,
    },
    {
        "ticker": "BETA3", "company_name": "Synthetic Beta", "sector": "Industrial",
        "current_price": 10.0, "dy_ttm": 0.105,
        "roe": 0.14, "roic": 0.10, "ebit_margin": 0.11, "net_margin": 0.07,
        "net_debt_ebitda": 2.8, "interest_coverage": 2.2, "current_ratio": 1.1, "debt_to_equity": 1.1,
        "cash_conversion": 0.72, "fcf_yield": 0.05, "fcf_margin": 0.04,
        "revenue_cagr_5y": 0.05, "eps_cagr_5y": 0.02, "fcf_cagr_5y": 0.01,
        "accrual_quality": 0.50, "piotroski_f": 5, "beneish_m": -1.4, "earnings_cash_consistency": 0.55,
        "dividend_regularity": 88, "dy_5y_median": 0.09, "dividend_cagr_5y": 0.02,
        "payout_sustainability": 50, "fcf_payout_sustainability": 45,
        "capital_allocation": 58, "governance": 66, "predictability": 55,
        "earnings_yield": 0.12, "fcf_yield_valuation": 0.05, "ev_ebit": 6.5, "pb": 1.1, "margin_of_safety": 0.22,
        "entry_value": 86, "distance_ma200_attractiveness": 82, "rsi_attractiveness": 80, "speculation_safety": 72,
        "news_score": 60, "rental_score": 90, "macro_score": 58, "liquidity_score": 72,
        "risk_score": 55, "short_pressure_score": 82, "entry_score": 82,
        "source_confidence": 0.95, "freshness_confidence": 0.96, "conflict_confidence": 0.95,
        "lending_rate_annual": 0.12, "lending_utilization": 0.19,
    },
    {
        "ticker": "GAMA3", "company_name": "Synthetic Gama", "sector": "Industrial",
        "current_price": 35.0, "dy_ttm": 0.03,
        "roe": 0.28, "roic": 0.25, "ebit_margin": 0.23, "net_margin": 0.17,
        "net_debt_ebitda": 0.2, "interest_coverage": 18.0, "current_ratio": 2.3, "debt_to_equity": 0.18,
        "cash_conversion": 1.25, "fcf_yield": 0.04, "fcf_margin": 0.15,
        "revenue_cagr_5y": 0.18, "eps_cagr_5y": 0.20, "fcf_cagr_5y": 0.19,
        "accrual_quality": 0.96, "piotroski_f": 9, "beneish_m": -2.6, "earnings_cash_consistency": 0.95,
        "dividend_regularity": 80, "dy_5y_median": 0.03, "dividend_cagr_5y": 0.12,
        "payout_sustainability": 95, "fcf_payout_sustainability": 94,
        "capital_allocation": 96, "governance": 94, "predictability": 94,
        "earnings_yield": 0.035, "fcf_yield_valuation": 0.04, "ev_ebit": 24.0, "pb": 6.0, "margin_of_safety": -0.18,
        "entry_value": 25, "distance_ma200_attractiveness": 20, "rsi_attractiveness": 18, "speculation_safety": 45,
        "news_score": 90, "rental_score": 45, "macro_score": 82, "liquidity_score": 96,
        "risk_score": 15, "short_pressure_score": 25, "entry_score": 28,
        "source_confidence": 0.99, "freshness_confidence": 0.99, "conflict_confidence": 0.99,
        "lending_rate_annual": 0.01, "lending_utilization": 0.01,
    },
]

red_flags = {"BETA3": [RedFlag(code="HIGH_SHORT_PRESSURE", reason="Synthetic example", blocking=False, severity=3)]}

for result in service.rank(rows, red_flags=red_flags):
    print(
        f"{result.ticker:6} final={result.final_score:5.1f} quality={result.company_quality_score:5.1f} "
        f"investment={result.investment_score:5.1f} entry={result.entry_score:5.1f} "
        f"confidence={result.data_confidence:5.1f}% {result.recommendation}"
    )
