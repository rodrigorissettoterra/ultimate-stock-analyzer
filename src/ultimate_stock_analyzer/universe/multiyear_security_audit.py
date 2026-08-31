from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.market.prices import PriceBar


@dataclass(frozen=True, slots=True)
class MultiyearTickerTradingEvidence:
    company_id: str
    ticker: str
    fca_years: tuple[int, ...]
    latest_fca_year: int
    latest_fca_security_type: str | None
    latest_fca_market: str | None
    latest_fca_administrator: str | None
    latest_fca_isin: str | None
    cotahist_trade_days: int
    first_trade_date: date | None
    last_trade_date: date | None
    b3_specifications: tuple[str, ...]
    b3_isins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MultiyearCompanyTradingEvidence:
    company_id: str
    status: str
    fca_tickers: tuple[str, ...]
    traded_tickers: tuple[str, ...]
    conflicting_tickers: tuple[str, ...]
    latest_trade_date: date | None


@dataclass(frozen=True, slots=True)
class MultiyearFcaCotahistAuditReport:
    candidate_company_ids: int
    fca_years: tuple[int, ...]
    fca_security_rows: int
    unique_fca_tickers: int
    ticker_identity_conflicts: dict[str, tuple[str, ...]]
    cotahist_year: int
    cotahist_matching_rows: int
    cotahist_latest_trade_date: date | None
    company_status_counts: dict[str, int]
    companies_with_exact_trading_evidence: tuple[str, ...]
    companies_without_fca_ticker_history: tuple[str, ...]
    companies_without_2026_spot_trade: tuple[str, ...]
    company_evidence: tuple[MultiyearCompanyTradingEvidence, ...]
    ticker_evidence: tuple[MultiyearTickerTradingEvidence, ...]
    scope: str = "CURRENT_FCA_5Y_PLUS_B3_COTAHIST_DIAGNOSTIC"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_multiyear_fca_against_cotahist(
    candidate_company_ids: Iterable[str],
    securities_by_year: Mapping[int, Iterable[SecurityRecord]],
    cotahist_bars: Iterable[PriceBar],
    *,
    cotahist_year: int,
) -> MultiyearFcaCotahistAuditReport:
    candidates = tuple(
        sorted({_canonical_company_id(value) for value in candidate_company_ids})
    )
    candidate_set = set(candidates)
    years = tuple(sorted(securities_by_year))
    if not years:
        raise ValueError("securities_by_year must contain at least one FCA year")

    records_by_ticker: defaultdict[str, list[tuple[int, SecurityRecord]]] = defaultdict(list)
    records_by_company: defaultdict[str, list[tuple[int, SecurityRecord]]] = defaultdict(list)
    total_security_rows = 0
    for year in years:
        for security in securities_by_year[year]:
            total_security_rows += 1
            ticker = _ticker(security.ticker)
            company_id = _canonical_company_id(security.company_id)
            records_by_ticker[ticker].append((year, security))
            if company_id in candidate_set:
                records_by_company[company_id].append((year, security))

    ticker_owners: dict[str, tuple[str, ...]] = {}
    for ticker, records in records_by_ticker.items():
        owners = tuple(
            sorted({_canonical_company_id(record.company_id) for _, record in records})
        )
        ticker_owners[ticker] = owners

    conflicts = {
        ticker: owners
        for ticker, owners in sorted(ticker_owners.items())
        if len(owners) > 1
    }

    bars_by_ticker: defaultdict[str, list[PriceBar]] = defaultdict(list)
    cotahist_rows = 0
    latest_cotahist_date: date | None = None
    for bar in cotahist_bars:
        if bar.trade_date.year != cotahist_year:
            continue
        ticker = _ticker(bar.ticker)
        if ticker not in records_by_ticker:
            continue
        cotahist_rows += 1
        bars_by_ticker[ticker].append(bar)
        if latest_cotahist_date is None or bar.trade_date > latest_cotahist_date:
            latest_cotahist_date = bar.trade_date

    ticker_evidence: list[MultiyearTickerTradingEvidence] = []
    ticker_evidence_by_company: defaultdict[
        str, list[MultiyearTickerTradingEvidence]
    ] = defaultdict(list)
    for ticker in sorted(records_by_ticker):
        owners = ticker_owners[ticker]
        if len(owners) != 1:
            continue
        company_id = owners[0]
        if company_id not in candidate_set:
            continue
        records = records_by_ticker[ticker]
        latest_year, latest_security = max(records, key=_security_rank)
        bars = sorted(bars_by_ticker.get(ticker, ()), key=lambda item: item.trade_date)
        evidence = MultiyearTickerTradingEvidence(
            company_id=company_id,
            ticker=ticker,
            fca_years=tuple(sorted({year for year, _ in records})),
            latest_fca_year=latest_year,
            latest_fca_security_type=_text(latest_security.security_type),
            latest_fca_market=_text(latest_security.market),
            latest_fca_administrator=_text(latest_security.administrator),
            latest_fca_isin=_text(latest_security.isin),
            cotahist_trade_days=len({bar.trade_date for bar in bars}),
            first_trade_date=bars[0].trade_date if bars else None,
            last_trade_date=bars[-1].trade_date if bars else None,
            b3_specifications=tuple(
                sorted({_text(bar.specification) for bar in bars if _text(bar.specification)})
            ),
            b3_isins=tuple(
                sorted({_text(bar.isin) for bar in bars if _text(bar.isin)})
            ),
        )
        ticker_evidence.append(evidence)
        ticker_evidence_by_company[company_id].append(evidence)

    company_evidence: list[MultiyearCompanyTradingEvidence] = []
    for company_id in candidates:
        company_records = records_by_company.get(company_id, ())
        all_company_tickers = tuple(
            sorted({_ticker(record.ticker) for _, record in company_records})
        )
        conflicting_tickers = tuple(
            sorted(
                ticker
                for ticker in all_company_tickers
                if ticker in conflicts and company_id in conflicts[ticker]
            )
        )
        unambiguous_tickers = tuple(
            ticker for ticker in all_company_tickers if ticker not in conflicts
        )
        evidences = ticker_evidence_by_company.get(company_id, ())
        traded_tickers = tuple(
            sorted(evidence.ticker for evidence in evidences if evidence.cotahist_trade_days > 0)
        )
        trade_dates = [
            evidence.last_trade_date
            for evidence in evidences
            if evidence.last_trade_date is not None
        ]
        if not all_company_tickers:
            status = "NO_FCA_TICKER_HISTORY"
        elif not unambiguous_tickers and conflicting_tickers:
            status = "ONLY_CONFLICTING_FCA_TICKERS"
        elif traded_tickers:
            status = "TRADED_EXACT_FCA_TICKER"
        else:
            status = "NO_2026_SPOT_TRADE_FOR_EXACT_FCA_TICKER"

        company_evidence.append(
            MultiyearCompanyTradingEvidence(
                company_id=company_id,
                status=status,
                fca_tickers=all_company_tickers,
                traded_tickers=traded_tickers,
                conflicting_tickers=conflicting_tickers,
                latest_trade_date=max(trade_dates) if trade_dates else None,
            )
        )

    counts = Counter(item.status for item in company_evidence)
    traded_companies = tuple(
        item.company_id
        for item in company_evidence
        if item.status == "TRADED_EXACT_FCA_TICKER"
    )
    no_history = tuple(
        item.company_id
        for item in company_evidence
        if item.status == "NO_FCA_TICKER_HISTORY"
    )
    no_trade = tuple(
        item.company_id
        for item in company_evidence
        if item.status == "NO_2026_SPOT_TRADE_FOR_EXACT_FCA_TICKER"
    )

    return MultiyearFcaCotahistAuditReport(
        candidate_company_ids=len(candidates),
        fca_years=years,
        fca_security_rows=total_security_rows,
        unique_fca_tickers=len(records_by_ticker),
        ticker_identity_conflicts=conflicts,
        cotahist_year=cotahist_year,
        cotahist_matching_rows=cotahist_rows,
        cotahist_latest_trade_date=latest_cotahist_date,
        company_status_counts=dict(sorted(counts.items())),
        companies_with_exact_trading_evidence=traded_companies,
        companies_without_fca_ticker_history=no_history,
        companies_without_2026_spot_trade=no_trade,
        company_evidence=tuple(company_evidence),
        ticker_evidence=tuple(ticker_evidence),
    )


def _security_rank(
    item: tuple[int, SecurityRecord],
) -> tuple[date, int, datetime, int]:
    year, security = item
    reference_date = security.reference_date or date.min
    available_from = security.available_from or datetime.min.replace(tzinfo=UTC)
    return reference_date, security.version, available_from, year


def _canonical_company_id(value: str) -> str:
    company_id = str(value).strip().lower()
    if not company_id.startswith("cvm:"):
        raise ValueError(f"company_id must use cvm:<CD_CVM>: {company_id}")
    code = company_id.split(":", 1)[1]
    if not code.isdigit():
        raise ValueError(f"company_id must use numeric CD_CVM: {company_id}")
    return f"cvm:{int(code)}"


def _ticker(value: str) -> str:
    ticker = str(value).strip().upper()
    if not ticker:
        raise ValueError("ticker must not be blank")
    return ticker


def _text(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None
