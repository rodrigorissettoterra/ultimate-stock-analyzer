from ultimate_stock_analyzer.market.prices import parse_cotahist_text


def _field(value: str, width: int) -> str:
    return value[:width].ljust(width)


def _numeric(value: int, width: int) -> str:
    return str(value).rjust(width, "0")


def _sample_line(ticker: str) -> str:
    parts = [
        _field("01", 2),
        _field("20241227", 8),
        _field("02", 2),
        _field(ticker, 12),
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


def test_parse_cotahist_can_filter_multiple_tickers() -> None:
    text = "\n".join([_sample_line("PETR4"), _sample_line("VALE3"), _sample_line("ITUB4")])
    bars = parse_cotahist_text(text, tickers=("petr4", "ITUB4"))
    assert [bar.ticker for bar in bars] == ["ITUB4", "PETR4"]


def test_parse_cotahist_rejects_conflicting_filters() -> None:
    try:
        parse_cotahist_text(_sample_line("PETR4"), ticker="PETR4", tickers=("PETR4",))
    except ValueError as exc:
        assert "ticker or tickers" in str(exc)
    else:
        raise AssertionError("expected conflicting ticker filters to fail")
