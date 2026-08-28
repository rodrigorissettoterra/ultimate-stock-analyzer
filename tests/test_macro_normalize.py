from ultimate_stock_analyzer.macro.models import MacroFactor
from ultimate_stock_analyzer.macro.normalize import normalize_bcb_sgs_rows, normalize_sidra_rows


def test_bcb_sgs_rows_become_canonical_macro_observations() -> None:
    rows = [{"data": "01/08/2026", "valor": "14.75"}]
    result = normalize_bcb_sgs_rows(
        rows,
        factor=MacroFactor.SELIC,
        series_code=432,
        unit="percent_per_year",
    )
    assert result[0].factor == MacroFactor.SELIC
    assert result[0].value == 14.75
    assert result[0].source == "BCB_SGS"


def test_sidra_missing_markers_are_not_converted_to_zero() -> None:
    rows = [
        {"PER": "202601", "V": "0,55"},
        {"PER": "202602", "V": "..."},
    ]
    result = normalize_sidra_rows(
        rows,
        factor=MacroFactor.INFLATION,
        table=9999,
        period_key="PER",
        unit="percent_per_month",
    )
    assert len(result) == 1
    assert result[0].value == 0.55
