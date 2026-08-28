from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile

import httpx
import pandas as pd

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"


@dataclass(slots=True)
class CVMCollector:
    user_agent: str = "ultimate-stock-analyzer/0.1"
    timeout_seconds: float = 60.0

    def dataset_url(self, document: str, year: int) -> str:
        doc = document.upper()
        if doc not in {"DFP", "ITR"}:
            raise ValueError("document must be DFP or ITR")
        return f"{CVM_BASE}/{doc}/DADOS/{doc.lower()}_cia_aberta_{year}.zip"

    def download_zip(self, document: str, year: int) -> bytes:
        url = self.dataset_url(document, year)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
            return response.content

    def list_csv_files(self, archive: bytes) -> list[str]:
        with ZipFile(BytesIO(archive)) as zf:
            return sorted(name for name in zf.namelist() if name.lower().endswith(".csv"))

    def read_csv(self, archive: bytes, filename: str) -> pd.DataFrame:
        with ZipFile(BytesIO(archive)) as zf, zf.open(filename) as f:
            return pd.read_csv(f, sep=";", encoding="latin1", low_memory=False)
