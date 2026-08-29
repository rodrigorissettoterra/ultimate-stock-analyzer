from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

APP_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesPage/classification?language=pt-br"
)
API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)

CLASSIFICATION_PAYLOADS: tuple[dict[str, Any], ...] = (
    {"language": "pt-br"},
)

COMPANY_PAYLOADS: tuple[dict[str, Any], ...] = (
    {"language": "pt-br", "pageNumber": 1, "pageSize": 2},
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
    response = client.get(f"{API_BASE}/{endpoint}/{_token(payload)}")
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


def _inspect_frontend(client: httpx.Client) -> None:
    response = client.get(APP_URL)
    response.raise_for_status()
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)', response.text)
    print(json.dumps({"frontend_scripts": scripts}, ensure_ascii=False))
    needles = (
        "GetIndustryClassification",
        "GetInitialCompanies",
        "subSectors",
        "describle",
    )
    for script in scripts:
        script_url = urljoin(str(response.url), script)
        js_response = client.get(script_url)
        if js_response.status_code != 200 or len(js_response.content) > 12_000_000:
            continue
        text = js_response.text
        for needle in needles:
            start = 0
            emitted = 0
            while emitted < 4:
                index = text.find(needle, start)
                if index < 0:
                    break
                left = max(0, index - 1200)
                right = min(len(text), index + 1800)
                print(
                    json.dumps(
                        {
                            "script": script,
                            "needle": needle,
                            "snippet": text[left:right],
                        },
                        ensure_ascii=False,
                    )
                )
                emitted += 1
                start = index + len(needle)


def main() -> None:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "ultimate-stock-analyzer/sector-probe",
        "Referer": APP_URL,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        for payload in CLASSIFICATION_PAYLOADS:
            _probe(client, "GetIndustryClassification", payload)
        for payload in COMPANY_PAYLOADS:
            _probe(client, "GetInitialCompanies", payload)
        _inspect_frontend(client)


if __name__ == "__main__":
    main()
