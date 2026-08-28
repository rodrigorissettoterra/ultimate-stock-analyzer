from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class MacroFactor(StrEnum):
    SELIC = "selic"
    INFLATION = "inflation"
    USD_BRL = "usd_brl"
    ACTIVITY = "activity"
    UNEMPLOYMENT = "unemployment"
    CREDIT_GROWTH = "credit_growth"
    LONG_RATES = "long_rates"
    COMMODITY_PRICE = "commodity_price"


@dataclass(frozen=True, slots=True)
class MacroObservation:
    factor: MacroFactor
    value: float
    reference_date: date
    unit: str
    source: str
    source_series: str
    publication_date: date | None = None


@dataclass(frozen=True, slots=True)
class FactorState:
    factor: MacroFactor
    latest_value: float
    reference_date: date
    level_percentile: float
    change_percentile: float | None
    state_signal: float
    confidence: float
    observations: int


@dataclass(frozen=True, slots=True)
class MacroSensitivity:
    factor: MacroFactor
    coefficient: float
    weight: float
    rationale: str

    def __post_init__(self) -> None:
        if not -1.0 <= self.coefficient <= 1.0:
            raise ValueError("macro sensitivity coefficient must be between -1 and 1")
        if self.weight <= 0:
            raise ValueError("macro sensitivity weight must be positive")


@dataclass(frozen=True, slots=True)
class MacroProfile:
    name: str
    version: str
    sensitivities: tuple[MacroSensitivity, ...]
    min_coverage: float
    min_confidence: float


@dataclass(frozen=True, slots=True)
class MacroAnalysis:
    profile: str
    score: float
    coverage: float
    confidence: float
    rankable: bool
    contributions: dict[str, float]
    states: dict[str, FactorState]
    flags: tuple[str, ...]
    model_version: str
