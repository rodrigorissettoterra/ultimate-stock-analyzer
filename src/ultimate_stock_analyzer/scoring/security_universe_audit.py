from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord


@dataclass(frozen=True, slots=True)
class SecurityTypeAuditRow:
    ticker: str
    company_id: str
    isin: str | None
    security_type: str | None
    market: str | None
    administrator: str | None
    reference_date: date | None
    version: int
    available_from: datetime | None
    source_document: str | None


@dataclass(frozen=True, slots=True)
class SecurityTypeAuditReport:
    requested_tickers: tuple[str, ...]
    found_tickers: tuple[str, ...]
    missing_tickers: tuple[str, ...]
    latest_rows: tuple[SecurityTypeAuditRow, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_security_types(
    securities: Iterable[SecurityRecord],
    *,
    tickers: Iterable[str],
) -> SecurityTypeAuditReport:
    requested = tuple(
        sorted(
            {
                str(ticker).strip().upper()
                for ticker in tickers
                if str(ticker).strip()
            }
        )
    )
    requested_set = set(requested)
    grouped: defaultdict[str, list[SecurityRecord]] = defaultdict(list)
    for security in securities:
        ticker = security.ticker.strip().upper()
        if ticker in requested_set:
            grouped[ticker].append(security)

    latest_rows: list[SecurityTypeAuditRow] = []
    for ticker in requested:
        candidates = grouped.get(ticker, [])
        if not candidates:
            continue
        latest = max(candidates, key=_security_rank)
        latest_rows.append(
            SecurityTypeAuditRow(
                ticker=ticker,
                company_id=latest.company_id,
                isin=latest.isin,
                security_type=latest.security_type,
                market=latest.market,
                administrator=latest.administrator,
                reference_date=latest.reference_date,
                version=latest.version,
                available_from=latest.available_from,
                source_document=latest.source_document,
            )
        )

    found = tuple(row.ticker for row in latest_rows)
    return SecurityTypeAuditReport(
        requested_tickers=requested,
        found_tickers=found,
        missing_tickers=tuple(sorted(requested_set - set(found))),
        latest_rows=tuple(latest_rows),
    )


def _security_rank(security: SecurityRecord) -> tuple[date, int, datetime]:
    reference_date = security.reference_date or date.min
    available_from = security.available_from or datetime.min.replace(tzinfo=UTC)
    return reference_date, security.version, available_from
