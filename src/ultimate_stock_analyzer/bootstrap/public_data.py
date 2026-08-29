from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.market.prices import B3CotahistCollector, PriceBar
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService

DEFAULT_DFP_STATEMENTS = ("BPA", "BPP", "DRE", "DFC_MI", "DFC_MD", "DVA")


@dataclass(frozen=True, slots=True)
class PublicDataBootstrapPlan:
    start_year: int
    end_year: int
    tickers: tuple[str, ...] = ()
    statements: tuple[str, ...] = DEFAULT_DFP_STATEMENTS
    document_type: str = "DFP"
    scope_token: str = "con"

    def __post_init__(self) -> None:
        current_year = datetime.now(UTC).year
        if self.start_year > self.end_year:
            raise ValueError("start_year must not be after end_year")
        if self.end_year >= current_year:
            raise ValueError(
                "annual public-data bootstrap accepts completed years only; "
                "use a year before the current UTC year"
            )
        normalized_tickers = tuple(
            dict.fromkeys(ticker.strip().upper() for ticker in self.tickers if ticker.strip())
        )
        if self.tickers and not normalized_tickers:
            raise ValueError("ticker filter contains no valid ticker")
        normalized_statements = tuple(
            dict.fromkeys(statement.strip().upper() for statement in self.statements if statement.strip())
        )
        if not normalized_statements:
            raise ValueError("at least one DFP statement is required")
        object.__setattr__(self, "tickers", normalized_tickers)
        object.__setattr__(self, "statements", normalized_statements)
        object.__setattr__(self, "document_type", self.document_type.strip().upper())
        object.__setattr__(self, "scope_token", self.scope_token.strip().lower())


class BootstrapArtifact(BaseModel):
    name: str
    source: str
    path: str
    sha256: str
    bytes: int = Field(ge=0)
    rows: int | None = Field(default=None, ge=0)
    reference_year: int | None = None
    raw: bool


class PublicDataBootstrapManifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    status: Literal["COMPLETE", "FAILED"]
    started_at: datetime
    completed_at: datetime
    start_year: int
    end_year: int
    requested_tickers: list[str]
    statements: list[str]
    source_policy: str = "official_free_only"
    artifacts: list[BootstrapArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class _CVMArchiveSource(Protocol):
    def download_registry_bytes(self) -> bytes: ...

    def download_zip(self, document: str, year: int) -> bytes: ...


class _CVMArchiveNormalizer(Protocol):
    def load_issuer_master_from_bytes(
        self,
        content: bytes,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]: ...

    def load_security_master_from_archive(
        self,
        archive: bytes,
        *,
        collected_at: datetime,
    ) -> list[SecurityRecord]: ...

    def load_statements_from_archive(
        self,
        archive: bytes,
        *,
        document_type: str,
        statements: tuple[str, ...],
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]: ...


class _PriceArchiveSource(Protocol):
    def download_year_archive(self, year: int) -> bytes: ...

    def parse_year_archive(
        self,
        content: bytes,
        *,
        tickers: tuple[str, ...] | None = None,
    ) -> list[PriceBar]: ...


class PublicDataBootstrapService:
    """Materialize exact public-source payloads and normalized historical records.

    This stage deliberately stops before investment scoring. Its output is the auditable,
    point-in-time input layer required by later universe scoring and walk-forward runs.
    """

    def __init__(
        self,
        data_dir: str | Path,
        *,
        cvm_source: _CVMArchiveSource | None = None,
        cvm_normalizer: _CVMArchiveNormalizer | None = None,
        price_source: _PriceArchiveSource | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        collector = cvm_source or CVMCollector()
        self.cvm_source = collector
        self.cvm_normalizer = cvm_normalizer or CVMIngestionService(collector=collector)
        self.price_source = price_source or B3CotahistCollector()

    def run(
        self,
        plan: PublicDataBootstrapPlan,
        *,
        collected_at: datetime | None = None,
        run_id: str | None = None,
    ) -> PublicDataBootstrapManifest:
        started_at = _aware(collected_at or datetime.now(UTC))
        resolved_run_id = run_id or _run_id(started_at)
        run_dir = self.data_dir / "bootstrap" / resolved_run_id
        if run_dir.exists():
            raise FileExistsError(f"bootstrap run already exists: {run_dir}")
        run_dir.mkdir(parents=True)

        artifacts: list[BootstrapArtifact] = []
        counts: dict[str, int] = {}
        warnings = [
            "B3 COTAHIST prices are preserved as raw, unadjusted historical quotes.",
            "This bootstrap does not create StockAnalysis rankings or promote model weights.",
        ]
        errors: list[str] = []

        try:
            registry_bytes = self.cvm_source.download_registry_bytes()
            artifacts.append(
                _write_bytes(
                    run_dir,
                    Path("raw/cvm/cad_cia_aberta.csv"),
                    registry_bytes,
                    name="cvm_issuer_registry_raw",
                    source="CVM_CAD",
                )
            )
            issuers = self.cvm_normalizer.load_issuer_master_from_bytes(
                registry_bytes,
                collected_at=started_at,
                active_only=False,
            )

            securities_by_year: dict[int, list[SecurityRecord]] = {}
            selected_company_ids: set[str] = set()
            seen_tickers: set[str] = set()

            for year in range(plan.start_year, plan.end_year + 1):
                fca_bytes = self.cvm_source.download_zip("FCA", year)
                artifacts.append(
                    _write_bytes(
                        run_dir,
                        Path(f"raw/cvm/fca_cia_aberta_{year}.zip"),
                        fca_bytes,
                        name="cvm_fca_raw",
                        source="CVM_FCA",
                        reference_year=year,
                    )
                )
                securities = self.cvm_normalizer.load_security_master_from_archive(
                    fca_bytes,
                    collected_at=started_at,
                )
                if plan.tickers:
                    requested = set(plan.tickers)
                    securities = [item for item in securities if item.ticker.upper() in requested]
                securities_by_year[year] = securities
                selected_company_ids.update(item.company_id for item in securities)
                seen_tickers.update(item.ticker.upper() for item in securities)
                artifacts.append(
                    _write_jsonl_gz(
                        run_dir,
                        Path(f"normalized/cvm/securities_{year}.jsonl.gz"),
                        securities,
                        name="cvm_security_master",
                        source="CVM_FCA",
                        reference_year=year,
                    )
                )

            if plan.tickers:
                missing_tickers = sorted(set(plan.tickers) - seen_tickers)
                if missing_tickers:
                    raise ValueError(
                        "requested tickers absent from FCA security master: "
                        + ", ".join(missing_tickers)
                    )
                issuers = [item for item in issuers if item.company_id in selected_company_ids]

            artifacts.append(
                _write_jsonl_gz(
                    run_dir,
                    Path("normalized/cvm/issuers.jsonl.gz"),
                    issuers,
                    name="cvm_issuer_master",
                    source="CVM_CAD",
                )
            )
            counts["issuers"] = len(issuers)
            counts["securities"] = sum(len(items) for items in securities_by_year.values())

            statement_count = 0
            price_count = 0
            for year in range(plan.start_year, plan.end_year + 1):
                dfp_bytes = self.cvm_source.download_zip(plan.document_type, year)
                artifacts.append(
                    _write_bytes(
                        run_dir,
                        Path(f"raw/cvm/{plan.document_type.lower()}_cia_aberta_{year}.zip"),
                        dfp_bytes,
                        name="cvm_financial_statements_raw",
                        source=f"CVM_{plan.document_type}",
                        reference_year=year,
                    )
                )
                statements = self.cvm_normalizer.load_statements_from_archive(
                    dfp_bytes,
                    document_type=plan.document_type,
                    statements=plan.statements,
                    scope_token=plan.scope_token,
                    collected_at=started_at,
                )
                if plan.tickers:
                    statements = [
                        item for item in statements if item.company_id in selected_company_ids
                    ]
                statement_count += len(statements)
                artifacts.append(
                    _write_jsonl_gz(
                        run_dir,
                        Path(f"normalized/cvm/dfp_{year}.jsonl.gz"),
                        statements,
                        name="cvm_financial_statements",
                        source=f"CVM_{plan.document_type}",
                        reference_year=year,
                    )
                )

                price_bytes = self.price_source.download_year_archive(year)
                artifacts.append(
                    _write_bytes(
                        run_dir,
                        Path(f"raw/b3/COTAHIST_A{year}.ZIP"),
                        price_bytes,
                        name="b3_cotahist_raw",
                        source="B3_COTAHIST",
                        reference_year=year,
                    )
                )
                prices = self.price_source.parse_year_archive(
                    price_bytes,
                    tickers=plan.tickers or None,
                )
                price_count += len(prices)
                artifacts.append(
                    _write_jsonl_gz(
                        run_dir,
                        Path(f"normalized/b3/cotahist_{year}.jsonl.gz"),
                        prices,
                        name="b3_cotahist",
                        source="B3_COTAHIST",
                        reference_year=year,
                    )
                )

            counts["financial_statement_lines"] = statement_count
            counts["price_bars"] = price_count
            manifest = PublicDataBootstrapManifest(
                run_id=resolved_run_id,
                status="COMPLETE",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                start_year=plan.start_year,
                end_year=plan.end_year,
                requested_tickers=list(plan.tickers),
                statements=list(plan.statements),
                artifacts=artifacts,
                counts=counts,
                warnings=warnings,
                errors=errors,
            )
            _write_manifest(run_dir, manifest)
            return manifest
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            manifest = PublicDataBootstrapManifest(
                run_id=resolved_run_id,
                status="FAILED",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                start_year=plan.start_year,
                end_year=plan.end_year,
                requested_tickers=list(plan.tickers),
                statements=list(plan.statements),
                artifacts=artifacts,
                counts=counts,
                warnings=warnings,
                errors=errors,
            )
            _write_manifest(run_dir, manifest)
            raise


def _run_id(started_at: datetime) -> str:
    return f"public-{started_at:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


def _write_bytes(
    run_dir: Path,
    relative_path: Path,
    content: bytes,
    *,
    name: str,
    source: str,
    reference_year: int | None = None,
) -> BootstrapArtifact:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return _artifact(
        run_dir,
        path,
        name=name,
        source=source,
        reference_year=reference_year,
        rows=None,
        raw=True,
    )


def _write_jsonl_gz(
    run_dir: Path,
    relative_path: Path,
    rows: list[Any],
    *,
    name: str,
    source: str,
    reference_year: int | None = None,
) -> BootstrapArtifact:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as file:
        for row in rows:
            payload = _json_payload(row)
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            file.write("\n")
    return _artifact(
        run_dir,
        path,
        name=name,
        source=source,
        reference_year=reference_year,
        rows=len(rows),
        raw=False,
    )


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _json_safe(asdict(value))
    return _json_safe(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _artifact(
    run_dir: Path,
    path: Path,
    *,
    name: str,
    source: str,
    reference_year: int | None,
    rows: int | None,
    raw: bool,
) -> BootstrapArtifact:
    content = path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source=source,
        path=path.relative_to(run_dir).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=rows,
        reference_year=reference_year,
        raw=raw,
    )


def _write_manifest(run_dir: Path, manifest: PublicDataBootstrapManifest) -> None:
    path = run_dir / "manifest.json"
    path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
