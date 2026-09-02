from datetime import date

from ultimate_stock_analyzer.backtesting.corporate_action_factor_validation import (
    AMBIGUOUS_FACTOR_TRANSFORM,
    DIRECT_FACTOR,
    EVENT_ISIN_MISMATCH,
    ONE_PLUS_FACTOR_PERCENT,
    summarize_factor_evidence,
    validate_corporate_action_factor,
)
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3StockActionContractRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


def _event(*, label: str, factor: float, isin: str = "BRTESTACNOR0") -> B3StockActionContractRecord:
    return B3StockActionContractRecord(
        asset_issued=isin,
        label=label,
        normalized_label=label,
        factor=factor,
        complete_factor=None,
        approved_on=date(2025, 1, 1),
        last_date_prior=date(2025, 1, 2),
        isin_code=isin,
        remarks=None,
        supported_label=True,
        ratio_new_per_old=None,
        factor_matches_complete_factor=None,
        conversion_status="SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR",
    )


def _bar(
    trade_date: date,
    *,
    open_price: float,
    close: float,
    isin: str = "BRTESTACNOR0",
) -> PriceBar:
    return PriceBar(
        ticker="TEST3",
        trade_date=trade_date,
        open=open_price,
        high=max(open_price, close),
        low=min(open_price, close),
        close=close,
        volume=1000.0,
        trades=10,
        quantity=100,
        isin=isin,
    )


def test_bonus_factor_prefers_one_plus_percentage() -> None:
    evidence = validate_corporate_action_factor(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="BONIFICACAO", factor=5.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=99.0, close=100.0),
            _bar(date(2025, 1, 3), open_price=95.24, close=96.0),
        ],
    )

    assert evidence.best_candidate == ONE_PLUS_FACTOR_PERCENT
    assert evidence.empirically_consistent
    assert evidence.ex_trade_date == "2025-01-03"


def test_reverse_split_factor_prefers_direct_ratio() -> None:
    evidence = validate_corporate_action_factor(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="GRUPAMENTO", factor=0.1),
        bars=[
            _bar(date(2025, 1, 2), open_price=9.8, close=10.0),
            _bar(date(2025, 1, 3), open_price=100.0, close=101.0),
        ],
    )

    assert evidence.best_candidate == DIRECT_FACTOR
    assert evidence.empirically_consistent


def test_split_percentage_factor_prefers_one_plus_percentage() -> None:
    evidence = validate_corporate_action_factor(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="DESDOBRAMENTO", factor=300.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=39.0, close=40.0),
            _bar(date(2025, 1, 3), open_price=10.0, close=10.2),
        ],
    )

    assert evidence.best_candidate == ONE_PLUS_FACTOR_PERCENT
    assert evidence.empirically_consistent


def test_event_isin_mismatch_fails_closed() -> None:
    evidence = validate_corporate_action_factor(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="BONIFICACAO", factor=5.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=99.0, close=100.0, isin="BROTHER00001"),
            _bar(date(2025, 1, 3), open_price=95.24, close=96.0, isin="BROTHER00001"),
        ],
    )

    assert EVENT_ISIN_MISMATCH in evidence.blockers
    assert evidence.best_candidate is None
    assert not evidence.empirically_consistent


def test_tied_transform_candidates_remain_ambiguous() -> None:
    evidence = validate_corporate_action_factor(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="GRUPAMENTO", factor=1.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
            _bar(date(2025, 1, 3), open_price=10.0, close=10.0),
        ],
    )

    assert evidence.best_candidate in {DIRECT_FACTOR, "INVERSE_FACTOR"}
    assert evidence.status == AMBIGUOUS_FACTOR_TRANSFORM
    assert not evidence.empirically_consistent


def test_label_promotion_requires_multiple_issuers() -> None:
    bars = [
        _bar(date(2025, 1, 2), open_price=99.0, close=100.0),
        _bar(date(2025, 1, 3), open_price=95.24, close=96.0),
    ]
    first = validate_corporate_action_factor(
        issuing_company="AAA",
        ticker="TEST3",
        event=_event(label="BONIFICACAO", factor=5.0),
        bars=bars,
    )
    second = validate_corporate_action_factor(
        issuing_company="BBB",
        ticker="TEST3",
        event=_event(label="BONIFICACAO", factor=5.0),
        bars=bars,
    )

    summary = summarize_factor_evidence([first, second])[0]

    assert summary.dominant_candidate == ONE_PLUS_FACTOR_PERCENT
    assert summary.empirically_consistent_event_count == 2
    assert summary.issuing_company_count == 2
    assert summary.promotion_ready
