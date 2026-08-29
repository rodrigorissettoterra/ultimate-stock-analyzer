from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.bootstrap import (
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


class FakeCVMSource:
    def __init__(self) -> None:
        self.zip_calls: list[tuple[str, int]] = []

    def download_registry_bytes(self) -> bytes:
        return b"registry-source"

    def download_zip(self, document: str, year: int) -> bytes:
        self.zip_calls.append((document, year))
        return f"{document}-{year}".encode()


class FakeCVMNormalizer:
    def load_issuer_master_from_bytes(
        self,
        content: bytes,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        assert content == b"registry-source"
        assert not active_only
        return [
            IssuerRecord(
                company_id="cvm:1",
                cvm_code=1,
                legal_name="Petro Teste S.A.",
                collected_at=collected_at,
            ),
            IssuerRecord(
                company_id="cvm:2",
                cvm_code=2,
                legal_name="Vale Teste S.A.",
                collected_at=collected_at,
            ),
        ]

    def load_security_master_from_archive(
        self,
        archive: bytes,
        *,
        collected_at: datetime,
    ) -> list[SecurityRecord]:
        year = int(archive.decode().split("-")[1])
        return [
            SecurityRecord(
                company_id="cvm:1",
                ticker="PETR4",
                reference_date=date(year, 12, 31),
                collected_at=collected_at,
            ),
            SecurityRecord(
                company_id="cvm:2",
                ticker="VALE3",
                reference_date=date(year, 12, 31),
                collected_at=collected_at,
            ),
        ]

    def load_statements_from_archive(
        self,
        archive: bytes,
        *,
        document_type: str,
        statements: tuple[str, ...],
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]:
        year = int(archive.decode().split("-")[1])
        return [
            _line("cvm:1", 1, "Petro Teste S.A.", year, collected_at),
            _line("cvm:2", 2, "Vale Teste S.A.", year, collected_at),
        ]


class FakePriceSource:
    def download_year_archive(self, year: int) -> bytes:
        return f"B3-{year}".encode()

    def parse_year_archive(
        self,
        content: bytes,
        *,
        tickers: tuple[str, ...] | None = None,
    ) -> list[PriceBar]:
        year = int(content.decode().split("-")[1])
        bars = [
            PriceBar(
                ticker="PETR4",
                trade_date=date(year, 12, 28),
                open=30.0,
                high=31.0,
                low=29.5,
                close=30.5,
                volume=1_000_000.0,
                trades=1000,
                quantity=50_000,
            ),
            PriceBar(
                ticker="VALE3",
                trade_date=date(year, 12, 28),
                open=60.0,
                high=61.0,
                low=59.5,
                close=60.5,
                volume=2_000_000.0,
                trades=2000,
                quantity=60_000,
            ),
        ]
        if tickers is None:
            return bars
        requested = set(tickers)
        return [bar for bar in bars if bar.ticker in requested]


def _line(
    company_id: str,
    cvm_code: int,
    company_name: str,
    year: int,
    collected_at: datetime,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id=company_id,
        cvm_code=cvm_code,
        company_name=company_name,
        document_type="DFP",
        statement="DRE",
        consolidation_scope="DF Consolidado",
        reference_date=date(year, 12, 31),
        account_code="3.01",
        account_name="Receita",
        value_brl=100.0,
        version=1,
        collected_at=collected_at,
    )


def test_bootstrap_materializes_raw_normalized_and_manifest(tmp_path: Path) -> None:
    cvm_source = FakeCVMSource()
    service = PublicDataBootstrapService(
        tmp_path,
        cvm_source=cvm_source,
        cvm_normalizer=FakeCVMNormalizer(),
        price_source=FakePriceSource(),
    )
    plan = PublicDataBootstrapPlan(
        start_year=2023,
        end_year=2024,
        tickers=("petr4",),
        statements=("DRE",),
    )

    manifest = service.run(
        plan,
        collected_at=datetime(2026, 8, 29, 12, tzinfo=UTC),
        run_id="test-run",
    )

    assert manifest.status == "COMPLETE"
    assert manifest.requested_tickers == ["PETR4"]
    assert manifest.counts == {
        "issuers": 1,
        "securities": 2,
        "financial_statement_lines": 2,
        "price_bars": 2,
    }
    assert cvm_source.zip_calls == [
        ("FCA", 2023),
        ("FCA", 2024),
        ("DFP", 2023),
        ("DFP", 2024),
    ]
    run_dir = tmp_path / "bootstrap" / "test-run"
    assert (run_dir / "raw/cvm/fca_cia_aberta_2023.zip").read_bytes() == b"FCA-2023"
    assert (run_dir / "raw/b3/COTAHIST_A2024.ZIP").read_bytes() == b"B3-2024"
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert saved_manifest["status"] == "COMPLETE"
    assert all(len(item["sha256"]) == 64 for item in saved_manifest["artifacts"])


def test_bootstrap_rejects_current_or_future_annual_year() -> None:
    with pytest.raises(ValueError, match="completed years only"):
        PublicDataBootstrapPlan(start_year=2025, end_year=9999)


def test_bootstrap_writes_failed_manifest(tmp_path: Path) -> None:
    class BrokenPriceSource(FakePriceSource):
        def download_year_archive(self, year: int) -> bytes:
            raise RuntimeError("source unavailable")

    service = PublicDataBootstrapService(
        tmp_path,
        cvm_source=FakeCVMSource(),
        cvm_normalizer=FakeCVMNormalizer(),
        price_source=BrokenPriceSource(),
    )
    plan = PublicDataBootstrapPlan(
        start_year=2024,
        end_year=2024,
        tickers=("PETR4",),
        statements=("DRE",),
    )

    with pytest.raises(RuntimeError, match="source unavailable"):
        service.run(plan, run_id="failed-run")

    saved = json.loads(
        (tmp_path / "bootstrap/failed-run/manifest.json").read_text(encoding="utf-8")
    )
    assert saved["status"] == "FAILED"
    assert "source unavailable" in saved["errors"][0]
