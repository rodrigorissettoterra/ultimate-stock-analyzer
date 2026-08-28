from pathlib import Path

from ultimate_stock_analyzer.domain.models import RedFlag
from ultimate_stock_analyzer.orchestration.service import AnalyzerService


def _service() -> AnalyzerService:
    root = Path(__file__).resolve().parents[1]
    return AnalyzerService(root / "config/scoring/model_v0.1.yml")


def _row(ticker: str, quality: float) -> dict[str, object]:
    return {
        "ticker": ticker,
        "sector": "Industrial",
        "roe": quality, "roic": quality, "ebit_margin": quality, "net_margin": quality,
        "net_debt_ebitda": 5 - quality * 10, "interest_coverage": quality * 20,
        "current_ratio": 1 + quality, "debt_to_equity": 2 - quality,
        "cash_conversion": quality, "fcf_yield": quality / 10, "fcf_margin": quality / 2,
        "revenue_cagr_5y": quality / 3, "eps_cagr_5y": quality / 3, "fcf_cagr_5y": quality / 3,
        "accrual_quality": quality, "piotroski_f": quality * 9, "beneish_m": -quality * 3,
        "earnings_cash_consistency": quality,
        "dividend_regularity": quality * 100, "dy_5y_median": quality / 10,
        "dividend_cagr_5y": quality / 5, "payout_sustainability": quality * 100,
        "fcf_payout_sustainability": quality * 100,
        "capital_allocation": quality * 100, "governance": quality * 100, "predictability": quality * 100,
        "earnings_yield": quality / 10, "fcf_yield_valuation": quality / 10,
        "ev_ebit": 20 - quality * 10, "pb": 5 - quality * 2, "margin_of_safety": quality / 4,
        "entry_value": quality * 100, "distance_ma200_attractiveness": quality * 100,
        "rsi_attractiveness": quality * 100, "speculation_safety": quality * 100,
        "news_score": 80, "rental_score": 50, "macro_score": 70, "liquidity_score": 90,
        "risk_score": 20, "short_pressure_score": 25, "entry_score": quality * 100,
        "source_confidence": 1.0, "freshness_confidence": 1.0, "conflict_confidence": 1.0,
    }


def test_better_company_ranks_higher() -> None:
    results = _service().rank([_row("GOOD3", 0.9), _row("MID3", 0.6), _row("WEAK3", 0.3)])
    assert [r.ticker for r in results] == ["GOOD3", "MID3", "WEAK3"]


def test_blocking_red_flag_overrides_score() -> None:
    flags = {"GOOD3": [RedFlag(code="AUDITOR_ADVERSE", reason="test", blocking=True, severity=5)]}
    results = _service().rank([_row("GOOD3", 0.9), _row("MID3", 0.6)], red_flags=flags)
    good = next(r for r in results if r.ticker == "GOOD3")
    assert good.recommendation.value == "BLOCKED"
