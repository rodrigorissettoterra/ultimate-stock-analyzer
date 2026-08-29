from __future__ import annotations

import base64
import json
from typing import Any

import httpx

BASE_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall/GetIndustryClassification"
)

PAYLOADS: tuple[dict[str, Any], ...] = (
    {"language": "pt-br"},
    {"language": "pt-br", "pageNumber": 1, "pageSize": 120},
    {"language": "pt-br", "pageNumber": 1, "pageSize": 9999},
)


def _token(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    return base64.b64encode(encoded).decode()


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            "type": "object",
            "keys": sorted(value)[:40],
            "sample": {
                key: _shape(value[key])
                for key in list(value)[:5]
            },
        }
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "first": _shape(value[0]) if value else None,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value)
        return {"type": type(value).__name__, "value": text[:160]}
    return {"type": type(value).__name__}


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
        for payload in PAYLOADS:
            url = f"{BASE_URL}/{_token(payload)}"
            try:
                response = client.get(url)
                print(
                    json.dumps(
                        {
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
                            "payload": payload,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )


if __name__ == "__main__":
    main()
