from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class ScoreSnapshot:
    ticker: str
    reference_date: date
    available_at: datetime
    investment_score: float
    entry_score: float | None = None
    rankable: bool = True
    model_version: str = "unknown"

    def __post_init__(self) -> None:
        if not 0.0 <= self.investment_score <= 100.0:
            raise ValueError("investment_score must be between 0 and 100")
        if self.entry_score is not None and not 0.0 <= self.entry_score <= 100.0:
            raise ValueError("entry_score must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class UniverseMembership:
    ticker: str
    start_date: date
    end_date: date | None = None

    def contains(self, as_of: date) -> bool:
        return self.start_date <= as_of and (self.end_date is None or as_of <= self.end_date)


@dataclass(frozen=True, slots=True)
class PricePoint:
    ticker: str
    trading_date: date
    close: float

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")


@dataclass(frozen=True, slots=True)
class ShareAction:
    ticker: str
    ex_date: date
    ratio_new_per_old: float

    def __post_init__(self) -> None:
        if self.ratio_new_per_old <= 0:
            raise ValueError("ratio_new_per_old must be positive")


@dataclass(frozen=True, slots=True)
class CashDistribution:
    ticker: str
    ex_date: date
    amount_per_share: float

    def __post_init__(self) -> None:
        if self.amount_per_share < 0:
            raise ValueError("amount_per_share cannot be negative")


@dataclass(frozen=True, slots=True)
class BacktestPolicy:
    top_n: int = 10
    min_investment_score: float = 0.0
    transaction_cost_bps: float = 10.0
    slippage_bps: float = 0.0
    initial_capital: float = 1.0
    strict_price_paths: bool = True

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be positive")
        if not 0.0 <= self.min_investment_score <= 100.0:
            raise ValueError("min_investment_score must be between 0 and 100")
        if self.transaction_cost_bps < 0 or self.slippage_bps < 0:
            raise ValueError("transaction costs and slippage cannot be negative")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")


@dataclass(frozen=True, slots=True)
class PeriodObservation:
    decision_date: date
    exit_decision_date: date
    portfolio_return: float
    benchmark_return: float
    turnover: float
    selected: tuple[str, ...]
    asset_returns: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BacktestResult:
    periods: tuple[PeriodObservation, ...]
    ending_equity: float
    model_versions: tuple[str, ...]
    warnings: tuple[str, ...] = ()
