from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any

import httpx
import pandas as pd

CVM_FOREIGN_REGISTRY_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
)


@dataclass(frozen=True, slots=True, order=True)
class CVMForeignIssuerRecord:
    company_id: str
    cvm_code: int
    legal_name: str
    registration_status: str | None
    registration_date: date | None
    cancellation_date: date | None
    collected_at: datetime
    source: str = "CVM_FOREIGN_ISSUER_CAD"


@dataclass(slots=True)
class CVMForeignIssuerCollector:
    user_agent: str = "ultimate-stock-analyzer/0.2"
    timeout_seconds: float = 60.0

    def registry_url(self) -> str:
        return CVM_FOREIGN_REGISTRY_URL

    def download_registry_bytes(self) -> bytes:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                self.registry_url(),
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        return response.content

    def read_registry_bytes(self, content: bytes) -> pd.DataFrame:
        return pd.read_csv(
            BytesIO(content),
            sep=";",
            encoding="latin1",
            low_memory=False,
        )

    def normalize(
        self,
        frame: pd.DataFrame,
        *,
        collected_at: datetime,
    ) -> list[CVMForeignIssuerRecord]:
        code_column = _required_column(frame, "CD_CVM", "COD_CVM")
        name_column = _required_column(frame, "DENOM_SOCIAL", "DENOM_CIA")
        status_column = _optional_column(frame, "SIT", "SIT_REG")
        registration_column = _optional_column(frame, "DT_REG")
        cancellation_column = _optional_column(frame, "DT_CANCEL")

        records: list[CVMForeignIssuerRecord] = []
        seen: set[tuple[object, ...]] = set()
        for row in frame.to_dict(orient="records"):
            code = _as_int(row.get(code_column))
            name = _as_text(row.get(name_column))
            if code is None or name is None:
                continue
            status = _as_text(row.get(status_column)) if status_column else None
            registration_date = (
                _as_date(row.get(registration_column)) if registration_column else None
            )
            cancellation_date = (
                _as_date(row.get(cancellation_column)) if cancellation_column else None
            )
            key = (code, name, status, registration_date, cancellation_date)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                CVMForeignIssuerRecord(
                    company_id=f"cvm:{code}",
                    cvm_code=code,
                    legal_name=name,
                    registration_status=status,
                    registration_date=registration_date,
                    cancellation_date=cancellation_date,
                    collected_at=collected_at,
                )
            )
        return sorted(records)

    def collect(self, *, collected_at: datetime) -> list[CVMForeignIssuerRecord]:
        return self.normalize(
            self.read_registry_bytes(self.download_registry_bytes()),
            collected_at=collected_at,
        )


def _required_column(frame: pd.DataFrame, *names: str) -> str:
    column = _optional_column(frame, *names)
    if column is None:
        raise ValueError(
            "CVM foreign issuer registry missing required column; "
            f"expected one of {names}, observed={sorted(map(str, frame.columns))}"
        )
    return column


def _optional_column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {str(column).strip().upper(): str(column) for column in frame.columns}
    for name in names:
        match = normalized.get(name.upper())
        if match is not None:
            return match
    return None


def _as_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(float(value))


def _as_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value, dayfirst=False).date()
