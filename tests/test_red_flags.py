from datetime import date

from ultimate_stock_analyzer.quality.red_flags import evaluate_red_flags


def test_blocking_red_flags() -> None:
    flags = evaluate_red_flags(equity=-1.0, as_of=date(2026, 8, 28))
    assert any(f.blocking and f.code == "NEGATIVE_EQUITY" for f in flags)
