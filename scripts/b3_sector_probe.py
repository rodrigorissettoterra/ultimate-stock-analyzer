from __future__ import annotations

import base64
import json
from typing import Any

import httpx

API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)

CLASSIFICATION_PAYLOADS: tuple[dict[str, Any], ...] = (
    {"language": "pt-br"},
)

COMPANY_PAYLOADS: tuple[dict[str, Any], ...] = (
    {"language": "pt-br", "pageNumber": 1, "pageSize": 2},
    {
        "language": "pt-br",
        "pageNumber": 1,
        "pageSize": 2,
        "sector": "Financeiro",
    },
    {
        "language": "pt-br",
        "pageNumber": 1,
        "pageSize": 2,
        "sector": "Bens Industriais",
    },
    {
        "language": "pt-br",
        "pageNumber": 1,
        "pageSize": 2,
        "sector": "___NO_SUCH_SECTOR___",
    },
)


def _token(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    return base64.b64encode(encoded).decode()


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        sample_keys = list(value)[:12]
        return {
            "type": "object",
            "keys": sorted(value)[:60],
            "sample": {key: _shape(value[key]) for key in sample_keys},
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "first": _shape(value[0]) if value else None,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return {"type": type(value).__name__, "value": str(value)[:160]}
    return {"type": type(value).__name__}


def _probe(client: httpx.Client, endpoint: str, payload: dict[str, Any]) -> None:
    url = f"{API_BASE}/{endpoint}/{_token(payload)}"
    try:
        response = client.get(url)
        print(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "payload": payload,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "bytes": len(response.content),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        try:
            body = response.json()
        except ValueError:
            print(json.dumps({"text_prefix": response.text[:500]}))
        else:
            print(json.dumps(_shape(body), ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "payload": payload,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def main() -> None:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "ultimate-stock-analyzer/sector-probe",
        "Referer": (
            "https://sistemaswebb3-listados.b3.com.br/"
            "listedCompaniesPage/classification?language=pt-br"
        ),
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        for payload in CLASSIFICATION_PAYLOADS:
            _probe(client, "GetIndustryClassification", payload)
        for payload in COMPANY_PAYLOADS:
            _probe(client, "GetInitialCompanies", payload)


if __name__ == "__main__":
    main()
