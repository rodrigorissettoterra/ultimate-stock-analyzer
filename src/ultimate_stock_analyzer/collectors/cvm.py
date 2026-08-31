from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile

import httpx
import pandas as pd

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
CVM_DOCUMENT_BASE = f"{CVM_BASE}/DOC"
CVM_REGISTRY_URL = f"{CVM_BASE}/CAD/DADOS/cad_cia_aberta.csv"


@dataclass(slots=True)
class CVMCollector:
    user_agent: str = "ultimate-stock-analyzer/0.2"
    timeout_seconds: float = 60.0
    connect_timeout_seconds: float = 15.0
    max_attempts: int = 3

    def dataset_url(self, document: str, year: int) -> str:
        doc = document.upper()
        if doc not in {"DFP", "ITR", "FCA"}:
            raise ValueError("document must be DFP, ITR or FCA")
        return f"{CVM_DOCUMENT_BASE}/{doc}/DADOS/{doc.lower()}_cia_aberta_{year}.zip"

    def registry_url(self) -> str:
        return CVM_REGISTRY_URL

    def download_zip(self, document: str, year: int) -> bytes:
        return self._download_bytes(self.dataset_url(document, year))

    def download_registry_bytes(self) -> bytes:
        return self._download_bytes(self.registry_url())

    def _download_bytes(self, url: str) -> bytes:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")

        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(self.connect_timeout_seconds, self.timeout_seconds),
        )
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = client.get(url, headers=headers)
                except httpx.TransportError:
                    if attempt == self.max_attempts:
                        raise
                    continue

                retryable_status = response.status_code == 429 or response.status_code >= 500
                if retryable_status and attempt < self.max_attempts:
                    continue
                response.raise_for_status()
                return response.content

        raise RuntimeError("CVM download exhausted without a response")

    def read_registry_bytes(self, content: bytes) -> pd.DataFrame:
        return pd.read_csv(
            BytesIO(content),
            sep=";",
            encoding="latin1",
            low_memory=False,
        )

    def download_registry(self) -> pd.DataFrame:
        return self.read_registry_bytes(self.download_registry_bytes())

    def list_csv_files(self, archive: bytes) -> list[str]:
        with ZipFile(BytesIO(archive)) as zf:
            return sorted(name for name in zf.namelist() if name.lower().endswith(".csv"))

    def read_csv(self, archive: bytes, filename: str) -> pd.DataFrame:
        with ZipFile(BytesIO(archive)) as zf, zf.open(filename) as csv_file:
            return pd.read_csv(
                csv_file,
                sep=";",
                encoding="latin1",
                low_memory=False,
            )

    def find_csv(self, archive: bytes, *tokens: str) -> str:
        normalized_tokens = tuple(token.lower() for token in tokens)
        matches = [
            name
            for name in self.list_csv_files(archive)
            if all(token in name.lower() for token in normalized_tokens)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one CSV matching {normalized_tokens}, found {len(matches)}"
            )
        return matches[0]
