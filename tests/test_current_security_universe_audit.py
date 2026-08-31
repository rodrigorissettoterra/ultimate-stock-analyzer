from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.universe.security_audit import (
    audit_current_security_universe,
)


def _security(
    company_id: str,
    ticker: str,
    security_type: str,
    *,
    reference_date: date,
    version: int = 1,
    trading_end: date | None = None,
) -> SecurityRecord:
    return SecurityRecord(
        company_id=company_id,
        ticker=ticker,
        security_type=security_type,
        market="Bolsa",
        administrator="B3",
        trading_start=date(2020, 1, 1),
        trading_end=trading_end,
        reference_date=reference_date,
        version=version,
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def test_security_audit_uses_latest_row_and_current_trading_bounds() -> None:
    securities = [
        _security("cvm:1", "ONE3", "Ações Ordinárias", reference_date=date(2025, 1, 1)),
        _security(
            "cvm:1",
            "ONE3",
            "Ações Ordinárias",
            reference_date=date(2026, 1, 1),
            version=2,
        ),
        _security(
            "cvm:2",
            "OLD3",
            "Ações Ordinárias",
            reference_date=date(2026, 1, 1),
            trading_end=date(2026, 1, 31),
        ),
        _security("cvm:3", "UNIT11", "Units", reference_date=date(2026, 1, 1)),
    ]

    report = audit_current_security_universe(
        securities,
        as_of=date(2026, 8, 31),
        selected_company_ids=("cvm:1", "cvm:2", "cvm:999"),
    )

    assert report.security_rows == 4
    assert report.latest_security_rows == 3
    assert report.active_latest_security_rows == 2
    assert report.security_type_counts == {"Ações Ordinárias": 1, "Units": 1}
    assert [row.company_id for row in report.selected_rows] == ["cvm:1", "cvm:2"]
    assert report.selected_rows[0].version == 2
    assert report.selected_rows[0].active_as_of is True
    assert report.selected_rows[1].active_as_of is False
    assert report.selected_company_ids_without_rows == ("cvm:999",)
    assert report.point_in_time_eligible is False
