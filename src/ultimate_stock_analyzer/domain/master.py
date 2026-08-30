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


class BankPrudentialAnnualRecord(BaseModel):
    """Annual bank evidence normalized from the official BCB IFData API.

    Identity is joined through the CVM issuer CNPJ root to the IFData prudential
    conglomerate leader. IFData historical rows are collected from the API's latest
    state and do not expose a revision history, so ``point_in_time_eligible`` remains
    false for strict historical backtests even when an estimated publication date is
    available.
    """

    company_id: str
    cvm_code: int
    cnpj: str | None = None
    cnpj_root: str
    fiscal_year: int
    reference_date: date
    ifdata_cod_inst: str
    ifdata_name: str
    institution_type: int = 1
    source_scope: str = "PRUDENTIAL_CONGLOMERATE"

    total_assets: float | None = None
    prior_total_assets: float | None = None
    equity: float | None = None
    prior_equity: float | None = None
    gross_credit_portfolio: float | None = None
    prior_gross_credit_portfolio: float | None = None

    annual_net_income: float | None = None
    annual_credit_loss_result: float | None = None
    annual_intermediation_income: float | None = None
    annual_intermediation_result: float | None = None
    annual_intermediation_expected_loss_result: float | None = None
    annual_payment_transactions_result: float | None = None
    annual_payment_expected_loss_result: float | None = None
    annual_bank_tariff_income: float | None = None
    annual_other_service_income: float | None = None
    annual_personnel_expense: float | None = None
    annual_administrative_expense: float | None = None

    basel_ratio: float | None = None
    tier1_ratio: float | None = None
    core_equity_tier1_ratio: float | None = None
    leverage_ratio: float | None = None

    roe: float | None = None
    roa: float | None = None
    cost_of_credit: float | None = None
    equity_to_assets: float | None = None
    efficiency_ratio: float | None = None
    fee_income_share: float | None = None

    available_from_estimate: datetime | None = None
    collected_at: datetime
    source: str = "BCB_IFDATA"
    source_documents: tuple[str, ...] = ()
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
