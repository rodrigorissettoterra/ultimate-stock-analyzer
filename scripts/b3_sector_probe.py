from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

import httpx

APP_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesPage/classification?language=pt-br"
)
API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)
XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


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


def _probe_json(client: httpx.Client, endpoint: str, payload: dict[str, Any]) -> None:
    response = client.get(f"{API_BASE}/{endpoint}/{_token(payload)}")
    response.raise_for_status()
    print(
        json.dumps(
            {
                "endpoint": endpoint,
                "payload": payload,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "bytes": len(response.content),
                "shape": _shape(response.json()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{XLSX_NS}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{XLSX_NS}t")))
    return strings


def _cell_value(cell: ElementTree.Element, strings: list[str]) -> str | None:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{XLSX_NS}is")
        if inline is None:
            return None
        return "".join(node.text or "" for node in inline.iter(f"{XLSX_NS}t"))
    value = cell.find(f"{XLSX_NS}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        return strings[int(value.text)]
    return value.text


def _inspect_xlsx(content: bytes) -> None:
    with ZipFile(BytesIO(content)) as zf:
        strings = _shared_strings(zf)
        workbook = ElementTree.fromstring(zf.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.get("Id"): rel.get("Target")
            for rel in relationships.findall(f"{PKG_REL_NS}Relationship")
        }
        sheets: list[dict[str, Any]] = []
        for sheet in workbook.findall(f"{XLSX_NS}sheets/{XLSX_NS}sheet"):
            name = sheet.get("name") or ""
            rel_id = sheet.get(f"{REL_NS}id")
            target = targets.get(rel_id)
            if target is None:
                continue
            path = target.lstrip("/")
            if not path.startswith("xl/"):
                path = f"xl/{path}"
            sheet_root = ElementTree.fromstring(zf.read(path))
            dimension = sheet_root.find(f"{XLSX_NS}dimension")
            rows: list[list[str | None]] = []
            for row in sheet_root.findall(
                f"{XLSX_NS}sheetData/{XLSX_NS}row"
            )[:18]:
                rows.append(
                    [_cell_value(cell, strings) for cell in row.findall(f"{XLSX_NS}c")]
                )
            sheets.append(
                {
                    "name": name,
                    "dimension": dimension.get("ref") if dimension is not None else None,
                    "preview_rows": rows,
                }
            )
        print(json.dumps({"workbook": sheets}, ensure_ascii=False, sort_keys=True))


def _probe_workbook(client: httpx.Client) -> None:
    payload = {"language": "pt-br"}
    response = client.get(
        f"{API_BASE}/GetDownloadIndustryClassification/{_token(payload)}"
    )
    response.raise_for_status()
    print(
        json.dumps(
            {
                "endpoint": "GetDownloadIndustryClassification",
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "bytes": len(response.content),
                "zip_magic": response.content[:2] == b"PK",
            },
            sort_keys=True,
        )
    )
    _inspect_xlsx(response.content)


def main() -> None:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "ultimate-stock-analyzer/sector-probe",
        "Referer": APP_URL,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        _probe_json(client, "GetIndustryClassification", {"language": "pt-br"})
        _probe_json(
            client,
            "GetInitialCompanies",
            {"language": "pt-br", "pageNumber": 1, "pageSize": 5000},
        )
        _probe_workbook(client)


if __name__ == "__main__":
    main()
