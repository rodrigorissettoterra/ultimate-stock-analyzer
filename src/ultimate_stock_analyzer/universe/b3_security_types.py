from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable


class B3SecurityKind(StrEnum):
    COMMON_SHARE = "COMMON_SHARE"
    PREFERRED_SHARE = "PREFERRED_SHARE"
    UNIT = "UNIT"
    SUBSCRIPTION_RECEIPT = "SUBSCRIPTION_RECEIPT"
    SUBSCRIPTION_BONUS = "SUBSCRIPTION_BONUS"
    SUBSCRIPTION_RIGHT = "SUBSCRIPTION_RIGHT"
    BDR = "BDR"
    VARIABLE_ROYALTY_TITLE = "VARIABLE_ROYALTY_TITLE"
    SHARE_DEPOSIT_CERTIFICATE = "SHARE_DEPOSIT_CERTIFICATE"
    FUND = "FUND"
    OTHER_UNKNOWN = "OTHER_UNKNOWN"


_CORE_EQUITY_KINDS = {
    B3SecurityKind.COMMON_SHARE,
    B3SecurityKind.PREFERRED_SHARE,
    B3SecurityKind.UNIT,
}
_COMMON_BASES = {"ON", "OR"}
_PREFERRED_BASES = {"PN", "PNA", "PNB", "PNC", "PND", "PNE"}
_BDR_BASES = {"BDR", "DR1", "DR2", "DR3", "DRE", "DRN"}
_FUND_BASES = {"CI", "FIDC"}


@dataclass(frozen=True, slots=True)
class B3SecuritySpecificationDecision:
    raw_specification: str
    normalized_specification: str
    base_token: str | None
    kind: B3SecurityKind
    core_equity_security: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True, slots=True)
class B3SecuritySpecificationSet:
    raw_specifications: tuple[str, ...]
    kinds: tuple[B3SecurityKind, ...]
    coherent_kind: B3SecurityKind | None
    core_equity_security: bool
    conflict: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "raw_specifications": list(self.raw_specifications),
            "kinds": [kind.value for kind in self.kinds],
            "coherent_kind": self.coherent_kind.value if self.coherent_kind else None,
            "core_equity_security": self.core_equity_security,
            "conflict": self.conflict,
        }


def classify_b3_security_specification(
    specification: str,
) -> B3SecuritySpecificationDecision:
    normalized = " ".join(str(specification).strip().upper().split())
    if not normalized:
        return _decision(
            specification,
            normalized,
            None,
            B3SecurityKind.OTHER_UNKNOWN,
            "blank or missing B3 ESPECI fails closed",
        )

    tokens = normalized.split()
    base = tokens[0]
    if "REC" in tokens and base in {*_COMMON_BASES, *_PREFERRED_BASES, "UNT", "M1"}:
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.SUBSCRIPTION_RECEIPT,
            "B3 ESPECI REC denotes a subscription receipt, not the underlying share",
        )
    if base == "BNS":
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.SUBSCRIPTION_BONUS,
            "B3 ESPECI BNS denotes a subscription bonus",
        )
    if base == "DIR":
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.SUBSCRIPTION_RIGHT,
            "B3 ESPECI DIR denotes a subscription right",
        )
    if base in _BDR_BASES:
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.BDR,
            "B3 ESPECI denotes a Brazilian Depositary Receipt class",
        )
    if base == "TPR":
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.VARIABLE_ROYALTY_TITLE,
            "TPR is a variable-remuneration title and is not an issuer share",
        )
    if base == "UNT":
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.UNIT,
            "B3 Unit is a deposit certificate composed of one or more security classes",
        )
    if base in _COMMON_BASES:
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.COMMON_SHARE,
            "B3 ESPECI denotes an ordinary/common share",
        )
    if base in _PREFERRED_BASES:
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.PREFERRED_SHARE,
            "B3 ESPECI denotes a preferred share class",
        )
    if base == "CDA":
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.SHARE_DEPOSIT_CERTIFICATE,
            "B3 ESPECI CDA is a share deposit certificate and is not auto-promoted to core equity",
        )
    if base in _FUND_BASES:
        return _decision(
            specification,
            normalized,
            base,
            B3SecurityKind.FUND,
            "B3 ESPECI denotes an investment-fund security",
        )
    return _decision(
        specification,
        normalized,
        base,
        B3SecurityKind.OTHER_UNKNOWN,
        "B3 ESPECI is outside the explicitly reviewed current security taxonomy",
    )


def classify_b3_security_specifications(
    specifications: Iterable[str],
) -> B3SecuritySpecificationSet:
    raw = tuple(sorted({str(item) for item in specifications if str(item).strip()}))
    decisions = tuple(classify_b3_security_specification(item) for item in raw)
    kinds = tuple(sorted({item.kind for item in decisions}, key=lambda item: item.value))
    coherent = kinds[0] if len(kinds) == 1 else None
    return B3SecuritySpecificationSet(
        raw_specifications=raw,
        kinds=kinds,
        coherent_kind=coherent,
        core_equity_security=coherent in _CORE_EQUITY_KINDS if coherent else False,
        conflict=len(kinds) > 1,
    )


def is_core_equity_kind(kind: B3SecurityKind) -> bool:
    return kind in _CORE_EQUITY_KINDS


def _decision(
    raw: str,
    normalized: str,
    base: str | None,
    kind: B3SecurityKind,
    reason: str,
) -> B3SecuritySpecificationDecision:
    return B3SecuritySpecificationDecision(
        raw_specification=str(raw),
        normalized_specification=normalized,
        base_token=base,
        kind=kind,
        core_equity_security=kind in _CORE_EQUITY_KINDS,
        reason=reason,
    )
