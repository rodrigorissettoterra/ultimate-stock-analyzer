from ultimate_stock_analyzer.collectors.b3_cotahist_securities import (
    parse_cotahist_security_line,
)


def _line(*, ticker: str, market: int, specification: str, isin: str) -> str:
    chars = [" "] * 245
    chars[0:2] = "01"
    chars[2:10] = "20260831"
    chars[12:24] = f"{ticker:<12}"[:12]
    chars[24:27] = f"{market:03d}"
    chars[39:49] = f"{specification:<10}"[:10]
    chars[230:242] = f"{isin:<12}"[:12]
    return "".join(chars)


def test_cotahist_security_observer_preserves_especi_and_isin() -> None:
    row = parse_cotahist_security_line(
        _line(
            ticker="ABCD3",
            market=10,
            specification="ON NM",
            isin="BRABCDACNOR1",
        )
    )
    assert row is not None
    assert row.ticker == "ABCD3"
    assert row.specification == "ON NM"
    assert row.isin == "BRABCDACNOR1"


def test_cotahist_security_observer_excludes_non_spot_market() -> None:
    assert (
        parse_cotahist_security_line(
            _line(
                ticker="ABCD3",
                market=20,
                specification="ON",
                isin="BRABCDACNOR1",
            )
        )
        is None
    )
