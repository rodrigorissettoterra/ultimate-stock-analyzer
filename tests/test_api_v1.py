from datetime import date

from fastapi.testclient import TestClient

from ultimate_stock_analyzer.api.main import create_app
from ultimate_stock_analyzer.api.repository import InMemoryAnalysisRepository
from ultimate_stock_analyzer.api.schemas import BacktestSummary, ScoreSet, StockAnalysis
from ultimate_stock_analyzer.scoring.integrated import DecisionStatus


def _analysis(
    ticker: str,
    *,
    sector: str,
    investment: float,
    status: DecisionStatus = DecisionStatus.ATTRACTIVE,
    rankable: bool = True,
) -> StockAnalysis:
    return StockAnalysis(
        ticker=ticker,
        company_name=f"Company {ticker}",
        sector=sector,
        as_of=date(2026, 8, 28),
        current_price=10.0,
        dy_ttm=0.06,
        scores=ScoreSet(
            company_quality=80.0,
            investment_attractiveness=investment,
            entry_timing=65.0,
            ranking_score=investment,
            actionability_score=investment * 0.85 + 65.0 * 0.15,
            data_confidence=92.0,
            component_confidence=0.90,
            status=status,
            rankable=rankable,
            model_version="1.4.0",
        ),
    )


def _client() -> TestClient:
    backtest = BacktestSummary(
        backtest_id="pit-v1",
        model_version="1.4.0",
        start_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        benchmark="IBOV",
        total_return=0.80,
        benchmark_total_return=0.50,
        cagr=0.10,
        benchmark_cagr=0.07,
        max_drawdown=-0.25,
        sharpe=0.8,
        average_turnover=0.30,
    )
    repository = InMemoryAnalysisRepository(
        analyses=[
            _analysis("AAA3", sector="Utilities", investment=84.0),
            _analysis("BBB4", sector="Banks", investment=76.0),
            _analysis(
                "CCC3",
                sector="Utilities",
                investment=90.0,
                status=DecisionStatus.INCONCLUSIVE,
                rankable=False,
            ),
        ],
        backtests=[backtest],
    )
    return TestClient(create_app(repository))


def test_ranking_is_investment_ordered_and_excludes_unrankable_by_default() -> None:
    response = _client().get("/v1/ranking")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [row["ticker"] for row in payload["items"]] == ["AAA3", "BBB4"]
    assert payload["items"][0]["rank"] == 1


def test_ranking_supports_sector_and_status_filters() -> None:
    response = _client().get("/v1/ranking", params={"sector": "Utilities", "status": "ATTRACTIVE"})
    assert response.status_code == 200
    assert [row["ticker"] for row in response.json()["items"]] == ["AAA3"]


def test_stock_scores_do_not_recalculate_financial_logic() -> None:
    response = _client().get("/v1/stocks/aaa3/scores")
    assert response.status_code == 200
    payload = response.json()
    assert payload["investment_attractiveness"] == 84.0
    assert payload["entry_timing"] == 65.0
    assert payload["model_version"] == "1.4.0"


def test_unknown_ticker_returns_404() -> None:
    response = _client().get("/v1/stocks/NOPE3")
    assert response.status_code == 404


def test_backtest_contract_and_metadata_are_exposed() -> None:
    client = _client()
    response = client.get("/v1/backtests/pit-v1")
    assert response.status_code == 200
    assert response.json()["benchmark"] == "IBOV"
    meta = client.get("/v1/meta")
    assert meta.status_code == 200
    assert "separate" in meta.json()["entry_semantics"]
