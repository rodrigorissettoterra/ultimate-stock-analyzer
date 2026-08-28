from datetime import date

from ultimate_stock_analyzer.market.prices import parse_cotahist_line


def _field(value: str, width: int) -> str:
    return value[:width].ljust(width)


def _numeric(value: int, width: int) -> str:
    return str(value).rjust(width, "0")


def _sample_line() -> str:
    parts = [
        _field("01", 2),
        _field("20260828", 8),
        _field("02", 2),
        _field("TEST3", 12),
        _numeric(10, 3),
        _field("TEST CORP", 12),
        _field("ON", 10),
        _field("", 3),
        _field("R$", 4),
        _numeric(1000, 13),
        _numeric(1100, 13),
        _numeric(950, 13),
        _numeric(1020, 13),
        _numeric(1050, 13),
        _numeric(1045, 13),
        _numeric(1055, 13),
        _numeric(123, 5),
        _numeric(456789, 18),
        _numeric(123456789, 18),
        _numeric(0, 13),
        _field("0", 1),
        _field("99991231", 8),
        _numeric(1, 7),
        _numeric(0, 13),
        _field("BRTESTACNOR0", 12),
        _numeric(1, 3),
    ]
    return "".join(parts)


def test_parse_cotahist_public_fixed_width_record() -> None:
    line = _sample_line()
    assert len(line) == 245
    bar = parse_cotahist_line(line)
    assert bar is not None
    assert bar.ticker == "TEST3"
    assert bar.trade_date == date(2026, 8, 28)
    assert bar.open == 10.0
    assert bar.high == 11.0
    assert bar.low == 9.5
    assert bar.close == 10.5
    assert bar.volume == 1_234_567.89
    assert bar.adjusted_close is None
    assert not bar.is_adjusted
