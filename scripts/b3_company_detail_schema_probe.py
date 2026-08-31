from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

B3_APP_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesPage/?language=pt-br"
)
B3_COMPANY_API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)

PROBE_COMPANIES = {
    "9512": "PETR",   # Petrobras positive control
    "27693": "BRST",  # Brisanet: false exclusion candidate
    "27634": "B100",  # B100: known current listed equity
    "8036": "LIGH",   # Light: missing from FCA-2026 candidate
    "18759": "BSCS",  # securitizer / no FCA-2026 security row
}

SEMANTIC_TOKENS = (
    "code",
    "ticker",
    "isin",
    "cnpj",
    "company",
    "trading",
    "issuing",
    "quotation",
    "market",
    "segment",
    "stock",
    "share",
    "quoted",
    "listing",
    "bdr",
)


def _detail_url(cvm_code: str) -> str:
    payload = json.dumps(
        {"codeCVM": str(cvm_code), "language": "pt-br"},
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    token = base64.b64encode(payload).decode()
    return f"{B3_COMPANY_API_BASE}/GetDetail/{token}"


def _flatten_scalars(value: Any, *, path: str = "$") -> dict[str, object]:
    output: dict[str, object] = {}
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            child = value[key]
            child_path = f"{path}.{key}"
            output.update(_flatten_scalars(child, path=child_path))
        return output
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            output.update(_flatten_scalars(child, path=f"{path}[{index}]"))
        if not value:
            output[path] = []
        return output
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 300:
            output[path] = value[:300] + "…"
        else:
            output[path] = value
        return output
    output[path] = f"<{type(value).__name__}>"
    return output


def _semantic_scalars(flattened: Mapping[str, object]) -> dict[str, object]:
    selected: dict[str, object] = {}
    for path, value in flattened.items():
        normalized = path.casefold()
        if any(token in normalized for token in SEMANTIC_TOKENS):
            selected[path] = value
    return selected


def _schema_paths(value: Any, *, path: str = "$") -> dict[str, str]:
    output: dict[str, str] = {path: type(value).__name__}
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            output.update(_schema_paths(value[key], path=f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value[:3]):
            output.update(_schema_paths(child, path=f"{path}[{index}]"))
    return output


def _probe_company(client: httpx.Client, cvm_code: str, label: str) -> dict[str, object]:
    response = client.get(_detail_url(cvm_code))
    response.raise_for_status()
    body = response.json()
    flattened = _flatten_scalars(body)
    top_level_keys = sorted(body) if isinstance(body, dict) else []
    return {
        "label": label,
        "requested_cvm_code": cvm_code,
        "http_status": response.status_code,
        "response_type": type(body).__name__,
        "top_level_keys": top_level_keys,
        "schema_paths": _schema_paths(body),
        "semantic_scalars": _semantic_scalars(flattened),
        "scalar_path_count": len(flattened),
    }


def main() -> None:
    collected_at = datetime.now(UTC)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "ultimate-stock-analyzer/0.2",
        "Referer": B3_APP_URL,
    }
    probes: list[dict[str, object]] = []
    with httpx.Client(
        timeout=60.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for cvm_code, label in PROBE_COMPANIES.items():
            probes.append(_probe_company(client, cvm_code, label))

    if not probes or any(probe["http_status"] != 200 for probe in probes):
        raise RuntimeError("B3 GetDetail schema probe did not return all HTTP 200 responses")

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES_GET_DETAIL",
        "scope": "SCHEMA_DISCOVERY_ONLY",
        "point_in_time_eligible": False,
        "probe_count": len(probes),
        "probes": probes,
        "notes": [
            "This artifact intentionally records schema paths and selected public scalar fields, not the complete raw B3 response.",
            "No ticker, ISIN, company identity or security eligibility decision is inferred in this block.",
            "The endpoint is queried by exact CVM code already established in the canonical B3 company catalog.",
        ],
    }
    Path("b3-company-detail-schema-probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
