from datetime import date

from ultimate_stock_analyzer.backtesting.b3_share_action_conversion import (
    CONVERTED_EMPIRICALLY_VALIDATED_LABEL,
    EMPIRICAL_FORMULA_MISMATCH,
    OFFICIAL_COMPLETE_FACTOR_CONFLICT,
    UNSUPPORTED_CONVERSION_LABEL,
    convert_b3_stock_action,
    expected_b3_share_ratio,
)
from ultimate_stock_analyzer.backtesting.models import PricePoint
from ultimate_stock_analyzer.backtesting.returns import total_holding_return
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3StockActionContractRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


def _event(
    *,
    label: str,
    factor: float,
    isin: str = "BRTESTACNOR0",
    complete_factor: str | None = None,
    ratio: float | None = None,
    conversion_status: str = "SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR",
) -> B3StockActionContractRecord:
    return B3StockActionContractRecord(
        asset_issued="TEST3",
        label=label,
        normalized_label=label,
        factor=factor,
        complete_factor=complete_factor,
        approved_on=date(2025, 1, 1),
        last_date_prior=date(2025, 1, 2),
        isin_code=isin,
        remarks=None,
        supported_label=label in {"BONIFICACAO", "DESDOBRAMENTO", "GRUPAMENTO"},
        ratio_new_per_old=ratio,
        factor_matches_complete_factor=None,
        conversion_status=conversion_status,
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


def test_validated_label_formulas_are_explicit() -> None:
    assert expected_b3_share_ratio("BONIFICACAO", 5.0) == (
        "ONE_PLUS_FACTOR_PERCENT",
        1.05,
    )
    assert expected_b3_share_ratio("DESDOBRAMENTO", 300.0) == (
        "ONE_PLUS_FACTOR_PERCENT",
        4.0,
    )
    assert expected_b3_share_ratio("GRUPAMENTO", 0.1) == ("DIRECT_FACTOR", 0.1)


def test_bonus_converts_to_share_action_on_first_ex_session() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="BONIFICACAO", factor=5.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=99.0, close=100.0),
            _bar(date(2025, 1, 3), open_price=95.24, close=96.0),
        ],
    )

    assert conversion.status == CONVERTED_EMPIRICALLY_VALIDATED_LABEL
    assert conversion.converted
    assert conversion.action is not None
    assert conversion.action.ex_date == date(2025, 1, 3)
    assert conversion.action.ratio_new_per_old == 1.05


def test_official_complete_factor_conflict_blocks_empirical_formula() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(
            label="DESDOBRAMENTO",
            factor=300.0,
            complete_factor="3 para 1",
            ratio=None,
            conversion_status="SUPPORTED_LABEL_FACTOR_CONFLICT",
        ),
        bars=[],
    )

    assert conversion.status == OFFICIAL_COMPLETE_FACTOR_CONFLICT
    assert not conversion.converted
    assert conversion.action is None


def test_unsupported_event_label_remains_blocked() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="EVENTO_ESPECIAL", factor=2.0),
        bars=[],
    )

    assert conversion.status == UNSUPPORTED_CONVERSION_LABEL
    assert not conversion.converted


def test_identity_or_formula_evidence_must_match_before_conversion() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="GRUPAMENTO", factor=0.1),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0, isin="BROTHER00001"),
            _bar(date(2025, 1, 3), open_price=100.0, close=101.0, isin="BROTHER00001"),
        ],
    )

    assert not conversion.converted
    assert conversion.action is None


def test_event_aware_return_removes_mechanical_split_jump() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="DESDOBRAMENTO", factor=300.0),
        bars=[
            _bar(date(2025, 1, 2), open_price=39.0, close=40.0),
            _bar(date(2025, 1, 3), open_price=10.0, close=10.2),
        ],
    )
    assert conversion.action is not None

    prices = [
        PricePoint(ticker="TEST3", trading_date=date(2025, 1, 2), close=40.0),
        PricePoint(ticker="TEST3", trading_date=date(2025, 1, 3), close=10.2),
    ]
    raw_return = total_holding_return(
        ticker="TEST3",
        entry_decision_date=date(2025, 1, 1),
        exit_decision_date=date(2025, 1, 2),
        prices=prices,
    )
    event_aware_return = total_holding_return(
        ticker="TEST3",
        entry_decision_date=date(2025, 1, 1),
        exit_decision_date=date(2025, 1, 2),
        prices=prices,
        share_actions=[conversion.action],
    )

    assert raw_return is not None
    assert event_aware_return is not None
    assert abs(event_aware_return) < abs(raw_return)
    assert abs(event_aware_return - 0.02) < 1e-12


def test_expected_formula_mismatch_fails_closed() -> None:
    conversion = convert_b3_stock_action(
        issuing_company="TEST",
        ticker="TEST3",
        event=_event(label="GRUPAMENTO", factor=0.5),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
            _bar(date(2025, 1, 3), open_price=5.0, close=5.1),
        ],
    )

    assert conversion.status == EMPIRICAL_FORMULA_MISMATCH
    assert not conversion.converted
