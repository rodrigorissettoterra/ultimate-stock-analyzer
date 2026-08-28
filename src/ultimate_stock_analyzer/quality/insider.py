from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class InsiderRole(StrEnum):
    CONTROLLER = "CONTROLLER"
    BOARD = "BOARD"
    EXECUTIVE = "EXECUTIVE"
    FISCAL_COUNCIL = "FISCAL_COUNCIL"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class InsiderTransaction:
    reference_date: date
    role: InsiderRole
    transaction_type: str
    quantity: float
    price: float | None
    source: str

    @property
    def notional(self) -> float | None:
        if self.price is None:
            return None
        return abs(self.quantity * self.price)


@dataclass(frozen=True, slots=True)
class InsiderAlignmentAnalysis:
    score: float
    confidence: float
    net_notional: float | None
    purchases: int
    sales: int
    flags: tuple[str, ...]


def analyze_insider_alignment(transactions: list[InsiderTransaction]) -> InsiderAlignmentAnalysis:
    if not transactions:
        return InsiderAlignmentAnalysis(
            score=50.0,
            confidence=0.0,
            net_notional=None,
            purchases=0,
            sales=0,
            flags=("NO_INSIDER_DATA",),
        )

    purchase_notional = 0.0
    sale_notional = 0.0
    priced = 0
    purchases = 0
    sales = 0
    for transaction in transactions:
        normalized = transaction.transaction_type.upper().strip()
        notional = transaction.notional
        if normalized in {"COMPRA", "BUY", "PURCHASE"}:
            purchases += 1
            if notional is not None:
                purchase_notional += notional
                priced += 1
        elif normalized in {"VENDA", "SELL", "SALE"}:
            sales += 1
            if notional is not None:
                sale_notional += notional
                priced += 1

    total = purchase_notional + sale_notional
    net = purchase_notional - sale_notional if priced else None
    score = 50.0 + (net / total) * 30.0 if total > 0 and net is not None else 50.0
    price_coverage = priced / max(purchases + sales, 1)
    sample_confidence = min(1.0, (purchases + sales) / 6.0)
    confidence = min(1.0, price_coverage * sample_confidence)
    flags: list[str] = []
    if sales >= 3 and sales > purchases * 2:
        flags.append("PERSISTENT_INSIDER_SELLING")
    if confidence < 0.40:
        flags.append("LOW_INSIDER_CONFIDENCE")
    return InsiderAlignmentAnalysis(
        score=max(0.0, min(100.0, score)),
        confidence=confidence,
        net_notional=net,
        purchases=purchases,
        sales=sales,
        flags=tuple(flags),
    )
