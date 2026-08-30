from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx

from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    IssuerRecord,
)

IFDATA_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata"
PRUDENTIAL_INSTITUTION_TYPE = 1

_CADASTRO_SELECT = (
    "CodInst,Data,NomeInstituicao,Tcb,Td,Tc,SegmentoTb,Atividade,Sr,"
    "CodConglomeradoFinanceiro,CodConglomeradoPrudencial,"
    "CnpjInstituicaoLider,Situacao"
)
_VALUES_SELECT = (
    "TipoInstituicao,CodInst,AnoMes,NomeRelatorio,NumeroRelatorio,"
    "Grupo,Conta,NomeColuna,DescricaoColuna,Saldo"
)

_REPORT_SUMMARY = "1"
_REPORT_INCOME = "4"
_REPORT_CAPITAL = "5"

# IFData report 1 changed its summary account identifiers at the 2025 COSIF
# transition. These mappings are explicit evidence contracts, not name-based
# inference. The pre-2025 identifiers were verified against the official
# 2024-12 prudential-conglomerate payload for C0080099.
_SUMMARY_ACCOUNTS_PRE_2025 = {
    "total_assets": "78182",
    "gross_credit_portfolio": "78183",
    "equity": "78186",
}
_SUMMARY_ACCOUNTS_2025 = {
    "total_assets": "140220",
    "equity": "140246",
    "gross_credit_portfolio": "141873",
}

_ACCOUNT_NET_INCOME = "141870"
_ACCOUNT_CREDIT_LOSS_RESULT = "141840"
_ACCOUNT_BASEL_RATIO = "79664"
_ACCOUNT_TIER1_RATIO = "79660"
_ACCOUNT_CET1_RATIO = "79659"
_ACCOUNT_LEVERAGE_RATIO = "79661"


@dataclass(frozen=True, slots=True)
class IFDataRawPayload:
    ano_mes: int
    kind: str
    content: bytes
    report_number: str | None = None


@dataclass(frozen=True, slots=True)
class IFDataPrudentialIdentity:
    ano_mes: int
    cod_inst: str
    name: str
    leader_cnpj_root: str
    prudential_code: str
    status: str


@dataclass(frozen=True, slots=True)
class IFDataAnnualCollection:
    fiscal_year: int
    profiles: tuple[BankPrudentialAnnualRecord, ...]
    raw_payloads: tuple[IFDataRawPayload, ...]
    warnings: tuple[str, ...] = ()


class BCBIFDataCollector:
    """Collect BCB IFData prudential-conglomerate evidence without fuzzy identity joins.

    The annual profile deliberately uses only fields whose meaning was verified against the
    official IFData report schema. The API exposes the latest state of historical rows rather
    than a revision history, so normalized profiles are *not* point-in-time eligible for strict
    historical backtests.
    """

    def __init__(self, *, timeout: float = 240.0) -> None:
        self.timeout = timeout

    def download_cadastro(self, ano_mes: int) -> bytes:
        return self._download(
            "IfDataCadastro(AnoMes=@AnoMes)",
            {
                "@AnoMes": ano_mes,
                "$format": "json",
                "$select": _CADASTRO_SELECT,
            },
        )

    def download_report(
        self,
        ano_mes: int,
        report_number: str,
        *,
        institution_type: int = PRUDENTIAL_INSTITUTION_TYPE,
    ) -> bytes:
        return self._download(
            (
                "IfDataValores("
                "AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
            ),
            {
                "@AnoMes": ano_mes,
                "@TipoInstituicao": institution_type,
                "@Relatorio": f"'{report_number}'",
                "$format": "json",
                "$select": _VALUES_SELECT,
            },
        )

    def collect_annual_bank_profiles(
        self,
        issuers: Iterable[IssuerRecord],
        *,
        fiscal_year: int,
        collected_at: datetime,
    ) -> IFDataAnnualCollection:
        issuer_rows = tuple(issuers)
        year_end = fiscal_year * 100 + 12
        prior_year_end = (fiscal_year - 1) * 100 + 12
        first_half_end = fiscal_year * 100 + 6

        current_cadastro = self.download_cadastro(year_end)
        raw_payloads: list[IFDataRawPayload] = [
            IFDataRawPayload(year_end, "cadastro", current_cadastro)
        ]

        current_identities: dict[str, IFDataPrudentialIdentity] = {}
        matched_issuers: list[IssuerRecord] = []
        warnings: list[str] = []
        for issuer in issuer_rows:
            if not issuer.cnpj:
                continue
            identity = resolve_prudential_identity(
                current_cadastro,
                cnpj=issuer.cnpj,
                ano_mes=year_end,
            )
            if identity is None:
                continue
            current_identities[issuer.company_id] = identity
            matched_issuers.append(issuer)

        if not matched_issuers:
            return IFDataAnnualCollection(
                fiscal_year=fiscal_year,
                profiles=(),
                raw_payloads=tuple(raw_payloads),
                warnings=(),
            )

        prior_cadastro = self.download_cadastro(prior_year_end)
        first_half_cadastro = self.download_cadastro(first_half_end)
        raw_payloads.extend(
            (
                IFDataRawPayload(prior_year_end, "cadastro", prior_cadastro),
                IFDataRawPayload(first_half_end, "cadastro", first_half_cadastro),
            )
        )

        report_payloads = {
            (prior_year_end, _REPORT_SUMMARY): self.download_report(
                prior_year_end, _REPORT_SUMMARY
            ),
            (first_half_end, _REPORT_INCOME): self.download_report(
                first_half_end, _REPORT_INCOME
            ),
            (year_end, _REPORT_SUMMARY): self.download_report(
                year_end, _REPORT_SUMMARY
            ),
            (year_end, _REPORT_INCOME): self.download_report(
                year_end, _REPORT_INCOME
            ),
            (year_end, _REPORT_CAPITAL): self.download_report(
                year_end, _REPORT_CAPITAL
            ),
        }
        for (ano_mes, report), content in report_payloads.items():
            raw_payloads.append(
                IFDataRawPayload(
                    ano_mes=ano_mes,
                    kind="report",
                    report_number=report,
                    content=content,
                )
            )

        profiles: list[BankPrudentialAnnualRecord] = []
        for issuer in matched_issuers:
            current_identity = current_identities[issuer.company_id]
            prior_identity = resolve_prudential_identity(
                prior_cadastro,
                cnpj=issuer.cnpj or "",
                ano_mes=prior_year_end,
            )
            first_half_identity = resolve_prudential_identity(
                first_half_cadastro,
                cnpj=issuer.cnpj or "",
                ano_mes=first_half_end,
            )
            if prior_identity is None or first_half_identity is None:
                warnings.append(
                    "IFData prudential identity history is incomplete for "
                    f"{issuer.company_id} in fiscal year {fiscal_year}."
                )

            profile = build_annual_bank_profile(
                issuer=issuer,
                fiscal_year=fiscal_year,
                current_identity=current_identity,
                prior_identity=prior_identity,
                first_half_identity=first_half_identity,
                prior_summary=report_payloads[(prior_year_end, _REPORT_SUMMARY)],
                first_half_income=report_payloads[(first_half_end, _REPORT_INCOME)],
                current_summary=report_payloads[(year_end, _REPORT_SUMMARY)],
                second_half_income=report_payloads[(year_end, _REPORT_INCOME)],
                current_capital=report_payloads[(year_end, _REPORT_CAPITAL)],
                collected_at=collected_at,
            )
            profiles.append(profile)

        return IFDataAnnualCollection(
            fiscal_year=fiscal_year,
            profiles=tuple(profiles),
            raw_payloads=tuple(raw_payloads),
            warnings=tuple(warnings),
        )

    def _download(self, path: str, params: dict[str, object]) -> bytes:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(f"{IFDATA_BASE_URL}/{path}", params=params)
            response.raise_for_status()
            return response.content


def cnpj_root(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        raise ValueError("CNPJ must contain at least eight digits")
    return digits[:8]


def resolve_prudential_identity(
    cadastro_content: bytes,
    *,
    cnpj: str,
    ano_mes: int,
) -> IFDataPrudentialIdentity | None:
    root = cnpj_root(cnpj)
    candidates = [
        row
        for row in _rows(cadastro_content)
        if _text(row.get("Situacao")) == "A"
        and _digits(row.get("CnpjInstituicaoLider")) == root
        and _text(row.get("CodConglomeradoPrudencial"))
        and _text(row.get("CodInst")) == _text(row.get("CodConglomeradoPrudencial"))
    ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError(
            "ambiguous IFData prudential identity for "
            f"CNPJ root {root} at {ano_mes}: {len(candidates)} rows"
        )
    row = candidates[0]
    cod_inst = _required_text(row.get("CodInst"))
    return IFDataPrudentialIdentity(
        ano_mes=ano_mes,
        cod_inst=cod_inst,
        name=_required_text(row.get("NomeInstituicao")),
        leader_cnpj_root=root,
        prudential_code=_required_text(row.get("CodConglomeradoPrudencial")),
        status=_required_text(row.get("Situacao")),
    )


def build_annual_bank_profile(
    *,
    issuer: IssuerRecord,
    fiscal_year: int,
    current_identity: IFDataPrudentialIdentity,
    prior_identity: IFDataPrudentialIdentity | None,
    first_half_identity: IFDataPrudentialIdentity | None,
    prior_summary: bytes,
    first_half_income: bytes,
    current_summary: bytes,
    second_half_income: bytes,
    current_capital: bytes,
    collected_at: datetime,
) -> BankPrudentialAnnualRecord:
    current_summary_rows = _institution_rows(
        current_summary, current_identity.cod_inst
    )
    current_capital_rows = _institution_rows(
        current_capital, current_identity.cod_inst
    )
    prior_summary_rows = (
        _institution_rows(prior_summary, prior_identity.cod_inst)
        if prior_identity is not None
        else []
    )
    first_half_rows = (
        _institution_rows(first_half_income, first_half_identity.cod_inst)
        if first_half_identity is not None
        else []
    )
    second_half_rows = _institution_rows(
        second_half_income, current_identity.cod_inst
    )

    current_summary_accounts = _summary_accounts(current_identity.ano_mes)
    prior_summary_accounts = (
        _summary_accounts(prior_identity.ano_mes)
        if prior_identity is not None
        else None
    )

    total_assets = _account_value(
        current_summary_rows, current_summary_accounts["total_assets"]
    )
    equity = _account_value(
        current_summary_rows, current_summary_accounts["equity"]
    )
    gross_credit = _account_value(
        current_summary_rows,
        current_summary_accounts["gross_credit_portfolio"],
    )
    prior_total_assets = (
        _account_value(prior_summary_rows, prior_summary_accounts["total_assets"])
        if prior_summary_accounts is not None
        else None
    )
    prior_equity = (
        _account_value(prior_summary_rows, prior_summary_accounts["equity"])
        if prior_summary_accounts is not None
        else None
    )
    prior_gross_credit = (
        _account_value(
            prior_summary_rows,
            prior_summary_accounts["gross_credit_portfolio"],
        )
        if prior_summary_accounts is not None
        else None
    )

    first_half_net_income = _account_value(first_half_rows, _ACCOUNT_NET_INCOME)
    second_half_net_income = _account_value(
        second_half_rows, _ACCOUNT_NET_INCOME
    )
    annual_net_income = _sum_required_pair(
        first_half_net_income, second_half_net_income
    )

    first_half_credit_loss = _account_value(
        first_half_rows, _ACCOUNT_CREDIT_LOSS_RESULT
    )
    second_half_credit_loss = _account_value(
        second_half_rows, _ACCOUNT_CREDIT_LOSS_RESULT
    )
    annual_credit_loss_result = _sum_required_pair(
        first_half_credit_loss, second_half_credit_loss
    )

    average_equity = _average_positive(prior_equity, equity)
    average_assets = _average_positive(prior_total_assets, total_assets)
    average_credit = _average_positive(prior_gross_credit, gross_credit)

    basel_ratio = _account_value(current_capital_rows, _ACCOUNT_BASEL_RATIO)
    tier1_ratio = _account_value(current_capital_rows, _ACCOUNT_TIER1_RATIO)
    cet1_ratio = _account_value(current_capital_rows, _ACCOUNT_CET1_RATIO)
    leverage_ratio = _account_value(
        current_capital_rows, _ACCOUNT_LEVERAGE_RATIO
    )

    return BankPrudentialAnnualRecord(
        company_id=issuer.company_id,
        cvm_code=issuer.cvm_code,
        cnpj=issuer.cnpj,
        cnpj_root=cnpj_root(issuer.cnpj or ""),
        fiscal_year=fiscal_year,
        reference_date=date(fiscal_year, 12, 31),
        ifdata_cod_inst=current_identity.cod_inst,
        ifdata_name=current_identity.name,
        institution_type=PRUDENTIAL_INSTITUTION_TYPE,
        total_assets=total_assets,
        prior_total_assets=prior_total_assets,
        equity=equity,
        prior_equity=prior_equity,
        gross_credit_portfolio=gross_credit,
        prior_gross_credit_portfolio=prior_gross_credit,
        annual_net_income=annual_net_income,
        annual_credit_loss_result=annual_credit_loss_result,
        basel_ratio=basel_ratio,
        tier1_ratio=tier1_ratio,
        core_equity_tier1_ratio=cet1_ratio,
        leverage_ratio=leverage_ratio,
        roe=_ratio(annual_net_income, average_equity),
        roa=_ratio(annual_net_income, average_assets),
        cost_of_credit=(
            _ratio(-annual_credit_loss_result, average_credit)
            if annual_credit_loss_result is not None
            else None
        ),
        equity_to_assets=_ratio(equity, total_assets),
        available_from_estimate=datetime(fiscal_year + 1, 4, 1, tzinfo=UTC),
        collected_at=_aware(collected_at),
        source_documents=(
            f"IFDataCadastro:{fiscal_year - 1}12",
            f"IFDataValores:{fiscal_year - 1}12:1",
            f"IFDataCadastro:{fiscal_year}06",
            f"IFDataValores:{fiscal_year}06:4",
            f"IFDataCadastro:{fiscal_year}12",
            f"IFDataValores:{fiscal_year}12:1",
            f"IFDataValores:{fiscal_year}12:4",
            f"IFDataValores:{fiscal_year}12:5",
        ),
        point_in_time_eligible=False,
    )


def bank_contract_values(record: BankPrudentialAnnualRecord) -> dict[str, float]:
    names = (
        "total_assets",
        "prior_total_assets",
        "equity",
        "prior_equity",
        "gross_credit_portfolio",
        "prior_gross_credit_portfolio",
        "annual_net_income",
        "annual_credit_loss_result",
        "basel_ratio",
        "tier1_ratio",
        "core_equity_tier1_ratio",
        "leverage_ratio",
    )
    values: dict[str, float] = {}
    for name in names:
        value = getattr(record, name)
        if value is not None:
            values[name] = float(value)
    return values


def _summary_accounts(ano_mes: int) -> dict[str, str]:
    return _SUMMARY_ACCOUNTS_2025 if ano_mes >= 202501 else _SUMMARY_ACCOUNTS_PRE_2025


def _rows(content: bytes) -> list[dict[str, Any]]:
    payload = json.loads(content)
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise TypeError("IFData response must contain a value list")
    return [dict(row) for row in payload["value"] if isinstance(row, dict)]


def _institution_rows(content: bytes, cod_inst: str) -> list[dict[str, Any]]:
    return [
        row
        for row in _rows(content)
        if _text(row.get("CodInst")) == cod_inst
    ]


def _account_value(rows: list[dict[str, Any]], account: str) -> float | None:
    matches = [
        row.get("Saldo")
        for row in rows
        if _text(row.get("Conta")) == account and row.get("Saldo") is not None
    ]
    if not matches:
        return None
    numeric = [float(value) for value in matches]
    if len(numeric) > 1 and any(value != numeric[0] for value in numeric[1:]):
        raise ValueError(f"ambiguous IFData balance for account {account}")
    return numeric[0]


def _sum_required_pair(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return first + second


def _average_positive(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    average = (first + second) / 2.0
    return average if average > 0 else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _text(value: object) -> str:
    return str(value or "").strip()


def _digits(value: object) -> str:
    return re.sub(r"\D", "", _text(value))


def _required_text(value: object) -> str:
    text = _text(value)
    if not text:
        raise ValueError("required IFData text value is missing")
    return text


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
