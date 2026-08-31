from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord


@dataclass(frozen=True, slots=True)
class CurrentSecurityAuditRow:
    company_id: str
    ticker: str
    security_type: str | None
    market: str | None
    administrator: str | None
    isin: str | None
    trading_start: date | None
    trading_end: date | None
    reference_date: date | None
    version: int
    active_as_of: bool


@dataclass(frozen=True, slots=True)
class CurrentSecurityUniverseAuditReport:
    security_rows: int
    latest_security_rows: int
    active_latest_security_rows: int
    security_type_counts: dict[str, int]
    market_counts: dict[str, int]
    administrator_counts: dict[str, int]
    selected_rows: tuple[CurrentSecurityAuditRow, ...]
    selected_company_ids_without_rows: tuple[str, ...]
    scope: str = "CURRENT_FCA_SNAPSHOT"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_current_security_universe(
    securities: Iterable[SecurityRecord],
    *,
    as_of: date,
    selected_company_ids: Iterable[str] = (),
) -> CurrentSecurityUniverseAuditReport:
    records = list(securities)
    selected = tuple(sorted({_canonical_company_id(value) for value in selected_company_ids}))
    selected_set = set(selected)

    grouped: defaultdict[tuple[str, str], list[SecurityRecord]] = defaultdict(list)
    for security in records:
        grouped[(security.company_id, security.ticker.strip().upper())].append(security)

    latest: list[SecurityRecord] = []
    for candidates in grouped.values():
        latest.append(max(candidates, key=_security_rank))
    latest.sort(key=lambda item: (item.company_id, item.ticker))

    active = [security for security in latest if _active_as_of(security, as_of=as_of)]
    security_type_counts = Counter(_label(item.security_type) for item in active)
    market_counts = Counter(_label(item.market) for item in active)
    administrator_counts = Counter(_label(item.administrator) for item in active)

    selected_rows = tuple(
        CurrentSecurityAuditRow(
            company_id=security.company_id,
            ticker=security.ticker.strip().upper(),
            security_type=security.security_type,
            market=security.market,
            administrator=security.administrator,
            isin=security.isin,
            trading_start=security.trading_start,
            trading_end=security.trading_end,
            reference_date=security.reference_date,
            version=security.version,
            active_as_of=_active_as_of(security, as_of=as_of),
        )
        for security in latest
        if security.company_id in selected_set
    )
    found_selected = {row.company_id for row in selected_rows}

    return CurrentSecurityUniverseAuditReport(
        security_rows=len(records),
        latest_security_rows=len(latest),
        active_latest_security_rows=len(active),
        security_type_counts=dict(sorted(security_type_counts.items())),
        market_counts=dict(sorted(market_counts.items())),
        administrator_counts=dict(sorted(administrator_counts.items())),
        selected_rows=selected_rows,
        selected_company_ids_without_rows=tuple(sorted(selected_set - found_selected)),
    )


def _active_as_of(security: SecurityRecord, *, as_of: date) -> bool:
    if security.trading_start is not None and security.trading_start > as_of:
        return False
    if security.trading_end is not None and security.trading_end < as_of:
        return False
    return True


def _security_rank(security: SecurityRecord) -> tuple[date, int, datetime]:
    reference_date = security.reference_date or date.min
    available_from = security.available_from or datetime.min.replace(tzinfo=UTC)
    return reference_date, security.version, available_from


def _canonical_company_id(value: str) -> str:
    company_id = str(value).strip().lower()
    if not company_id.startswith("cvm:"):
        raise ValueError(f"company_id must use cvm:<CD_CVM>: {company_id}")
    code = company_id.split(":", 1)[1]
    if not code.isdigit():
        raise ValueError(f"company_id must use numeric CD_CVM: {company_id}")
    return f"cvm:{int(code)}"


def _label(value: str | None) -> str:
    text = str(value or "").strip()
    return text or "<MISSING>"
