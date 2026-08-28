from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

CVM_DATA_HOST = "dados.cvm.gov.br"


def parse_cvm_structured_zip(content: bytes) -> dict[str, list[dict[str, str]]]:
    """Parse the CSV members of one official CVM structured-data ZIP.

    CVM structured files are commonly semicolon-delimited and encoded as latin1/Windows-1252.
    The parser preserves source column names and values; semantic mapping is handled separately.
    """
    datasets: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".csv"):
                continue
            raw = archive.read(member)
            text = _decode_cvm(raw)
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            stem = member.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            datasets[stem] = [
                {str(key): "" if value is None else str(value) for key, value in row.items()}
                for row in reader
            ]
    return datasets


def select_dataset(
    datasets: dict[str, list[dict[str, str]]],
    name_contains: str,
) -> list[dict[str, str]]:
    needle = name_contains.casefold()
    matches = [rows for name, rows in datasets.items() if needle in name.casefold()]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one CVM dataset matching {name_contains!r}")
    return matches[0]


@dataclass(slots=True)
class CVMStructuredZipCollector:
    timeout_seconds: float = 60.0
    user_agent: str = "ultimate-stock-analyzer/1.0"

    def fetch(self, url: str) -> dict[str, list[dict[str, str]]]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != CVM_DATA_HOST:
            raise ValueError("CVM structured collector only accepts official dados.cvm.gov.br HTTPS URLs")
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
        return parse_cvm_structured_zip(response.content)


def _decode_cvm(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unable to decode CVM CSV member")
