from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class IssuerRecord(BaseModel):
    company_id: str
    cvm_code: int
    cnpj: str | None = None
    legal_name: str
    trade_name: str | None = None
    registration_status: str | None = None
    registration_date: date | None = None
    cancellation_date: date | None = None
    collected_at: datetime
    source: str = "CVM"


class SecurityRecord(BaseModel):
    company_id: str
    ticker: str
    isin: str | None = None
    security_type: str | None = None
    market: str | None = None
    administrator: str | None = None
    trading_start: date | None = None
    trading_end: date | None = None
    reference_date: date | None = None
    version: int = 0
    available_from: datetime | None = None
    collected_at: datetime
    source: str = "CVM_FCA"
    source_document: str | None = None


class SectorClassificationRecord(BaseModel):
    """Current B3 economic classification snapshot for one CVM issuer.

    The official B3 workbook is a current snapshot, not a historical point-in-time
    series. ``point_in_time_eligible`` therefore remains false by contract so the
    record cannot silently be reused as historical sector evidence in walk-forward
    tests.
    """

    company_id: str
    cvm_code: int
    cnpj: str | None = None
    issuer_code: str
    trading_name: str
    sector: str
    subsector: str
    segment: str
    listing_segment: str | None = None
    collected_at: datetime
    source: str = "B3_INDUSTRY_CLASSIFICATION"
    source_document: str = "ClassifSetorial.xlsx"
    snapshot_scope: str = "CURRENT"
    point_in_time_eligible: bool = False


class FinancialStatementLine(BaseModel):
    company_id: str
    cvm_code: int
    cnpj: str | None = None
    company_name: str
    document_type: str
    statement: str
    consolidation_scope: str | None = None
    reference_date: date
    period_start: date | None = None
    period_end: date | None = None
    fiscal_order: str | None = None
    account_code: str
    account_name: str
    value_brl: float
    currency: str = "BRL"
    source_scale: str | None = None
    version: int
    document_id: int | None = None
    received_at: datetime | None = None
    available_from: datetime | None = None
    collected_at: datetime
    source: str = "CVM"
    source_document: str | None = None
