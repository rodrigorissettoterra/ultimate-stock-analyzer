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
    annual_administrative_expense: float | None = None
    annual_operating_result_ex_provisions: float | None = None
    annual_service_income: float | None = None
    annual_financial_intermediation_income: float | None = None

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


class InsuranceSusepAnnualRecord(BaseModel):
    """Annual insurer evidence normalized from official SUSEP public sources.

    The initial contract is intentionally fail-closed. The SES public database is
    refreshed weekly and explicitly allows historical values to be changed by data
    reloads, so current downloads are not considered revision-aware point-in-time
    evidence. Scoring metrics remain optional until their exact official SES/FIP
    field mappings and formulas are independently verified.
    """

    company_id: str
    cvm_code: int
    cnpj: str | None = None
    fiscal_year: int
    reference_date: date
    susep_company_code: str
    susep_name: str
    source_scope: str = "SUPERVISED_INSURER"

    total_assets: float | None = None
    equity: float | None = None
    annual_net_income: float | None = None
    annual_earned_premiums: float | None = None
    annual_incurred_claims: float | None = None
    annual_acquisition_expense: float | None = None
    annual_administrative_expense: float | None = None
    technical_provisions: float | None = None
    adjusted_equity_pla: float | None = None
    minimum_required_capital_cmr: float | None = None
    guaranteed_assets: float | None = None
    required_technical_provision_coverage: float | None = None

    roe: float | None = None
    roa: float | None = None
    combined_ratio: float | None = None
    loss_ratio: float | None = None
    expense_ratio: float | None = None
    solvency_ratio: float | None = None
    capital_adequacy_ratio: float | None = None
    technical_provisions_coverage: float | None = None

    available_from_estimate: datetime | None = None
    collected_at: datetime
    source: str = "SUSEP_SES"
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
