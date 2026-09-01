from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from ultimate_stock_analyzer.collectors.bcb_ifdata import (
    IFDataPrudentialIdentity,
    bank_contract_values,
    cnpj_root,
    resolve_prudential_identity,
)
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    IssuerRecord,
)
from ultimate_stock_analyzer.fundamentals.contracts import (
    BANK_PRUDENTIAL_CONTRACT,
    evaluate_contract,
)

IFDataApplicabilityStatus = Literal[
    "EXACT_PRUDENTIAL_IDENTITY_FOUND",
    "NO_PRUDENTIAL_IDENTITY",
]


@dataclass(frozen=True, slots=True)
class IFDataIssuerApplicabilityAudit:
    company_id: str
    cvm_code: int
    cnpj: str
    cnpj_root: str
    ano_mes: int
    status: IFDataApplicabilityStatus
    prudential_identity: IFDataPrudentialIdentity | None
    bank_profile_available: bool
    bank_contract_critical_coverage: float | None
    bank_contract_total_coverage: float | None
    bank_contract_missing_critical: tuple[str, ...]
    bank_contract_missing_supporting: tuple[str, ...]
    bank_profile_metrics: dict[str, float | None]
    scope: str = "CURRENT_IFDATA_PRUDENTIAL_APPLICABILITY_DIAGNOSTIC"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_ifdata_issuer_applicability(
    *,
    issuer: IssuerRecord,
    cadastro_content: bytes,
    ano_mes: int,
    profile: BankPrudentialAnnualRecord | None = None,
) -> IFDataIssuerApplicabilityAudit:
    """Audit exact CVM-issuer-to-BCB-IFData applicability without fuzzy matching."""

    if not issuer.cnpj:
        raise ValueError(
            "IFData applicability audit requires an official issuer CNPJ: "
            f"company_id={issuer.company_id}"
        )

    identity = resolve_prudential_identity(
        cadastro_content,
        cnpj=issuer.cnpj,
        ano_mes=ano_mes,
    )
    if identity is None:
        if profile is not None:
            raise ValueError(
                "Bank profile cannot be supplied when no exact IFData prudential "
                f"identity exists: company_id={issuer.company_id}"
            )
        return IFDataIssuerApplicabilityAudit(
            company_id=issuer.company_id,
            cvm_code=issuer.cvm_code,
            cnpj=issuer.cnpj,
            cnpj_root=cnpj_root(issuer.cnpj),
            ano_mes=ano_mes,
            status="NO_PRUDENTIAL_IDENTITY",
            prudential_identity=None,
            bank_profile_available=False,
            bank_contract_critical_coverage=None,
            bank_contract_total_coverage=None,
            bank_contract_missing_critical=(),
            bank_contract_missing_supporting=(),
            bank_profile_metrics={},
        )

    if profile is not None:
        if profile.company_id != issuer.company_id:
            raise ValueError(
                "IFData bank profile company identity does not match issuer: "
                f"issuer={issuer.company_id} profile={profile.company_id}"
            )
        if profile.cnpj_root != identity.leader_cnpj_root:
            raise ValueError(
                "IFData bank profile CNPJ root does not match prudential identity: "
                f"company_id={issuer.company_id}"
            )
        coverage = evaluate_contract(
            bank_contract_values(profile),
            BANK_PRUDENTIAL_CONTRACT,
        )
        metrics = _profile_metrics(profile)
    else:
        coverage = None
        metrics = {}

    return IFDataIssuerApplicabilityAudit(
        company_id=issuer.company_id,
        cvm_code=issuer.cvm_code,
        cnpj=issuer.cnpj,
        cnpj_root=cnpj_root(issuer.cnpj),
        ano_mes=ano_mes,
        status="EXACT_PRUDENTIAL_IDENTITY_FOUND",
        prudential_identity=identity,
        bank_profile_available=profile is not None,
        bank_contract_critical_coverage=(
            coverage.critical_coverage if coverage is not None else None
        ),
        bank_contract_total_coverage=(
            coverage.total_coverage if coverage is not None else None
        ),
        bank_contract_missing_critical=(
            coverage.missing_critical if coverage is not None else ()
        ),
        bank_contract_missing_supporting=(
            coverage.missing_supporting if coverage is not None else ()
        ),
        bank_profile_metrics=metrics,
    )


def _profile_metrics(
    profile: BankPrudentialAnnualRecord,
) -> dict[str, float | None]:
    names = (
        "total_assets",
        "equity",
        "gross_credit_portfolio",
        "annual_net_income",
        "annual_credit_loss_result",
        "basel_ratio",
        "tier1_ratio",
        "core_equity_tier1_ratio",
        "leverage_ratio",
        "roe",
        "roa",
        "cost_of_credit",
        "equity_to_assets",
        "efficiency_ratio",
        "fee_income_share",
    )
    return {name: getattr(profile, name) for name in names}
