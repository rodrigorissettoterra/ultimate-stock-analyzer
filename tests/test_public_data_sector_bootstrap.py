from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.bootstrap import PublicDataBootstrapPlan, PublicDataBootstrapService
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SectorClassificationRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


class _CVMSource:
    def download_registry_bytes(self) -> bytes:
        return b"registry"

    def download_zip(self, document: str, year: int) -> bytes:
        return f"{document}-{year}".encode()


class _Normalizer:
    def load_issuer_master_from_bytes(
        self,
        content: bytes,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        return [
            IssuerRecord(
                company_id="cvm:1",
                cvm_code=1,
                legal_name="Teste S.A.",
                collected_at=collected_at,
            )
        ]

    def load_security_master_from_archive(
        self,
        archive: bytes,
        *,
        collected_at: datetime,
    ) -> list[SecurityRecord]:
        return [
            SecurityRecord(
                company_id="cvm:1",
                ticker="TEST3",
                reference_date=date(2024, 12, 31),
                collected_at=collected_at,
            )
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
        return [
            FinancialStatementLine(
                company_id="cvm:1",
                cvm_code=1,
                company_name="Teste S.A.",
                document_type=document_type,
                statement="DRE",
                consolidation_scope="DF Consolidado",
                reference_date=date(2024, 12, 31),
                fiscal_order="ÚLTIMO",
                account_code="3.01",
                account_name="Receita",
                value_brl=100.0,
                version=1,
                collected_at=collected_at,
            )
        ]


class _Prices:
    def download_year_archive(self, year: int) -> bytes:
        return b"prices"

    def parse_year_archive(
        self,
        content: bytes,
        *,
        tickers: tuple[str, ...] | None = None,
    ) -> list[PriceBar]:
        return [
            PriceBar(
                ticker="TEST3",
                trade_date=date(2024, 12, 30),
                open=10.0,
                high=10.5,
                low=9.5,
                close=10.0,
                volume=1000.0,
                trades=10,
                quantity=100,
            )
        ]


class _Classification:
    def download_workbook(self) -> bytes:
        return b"xlsx-source"

    def download_company_catalog_archive(self) -> bytes:
        return b"catalog-source"

    def normalize(
        self,
        workbook_content: bytes,
        company_catalog_archive: bytes,
        *,
        collected_at: datetime,
    ) -> list[SectorClassificationRecord]:
        assert workbook_content == b"xlsx-source"
        assert company_catalog_archive == b"catalog-source"
        return [
            SectorClassificationRecord(
                company_id="cvm:1",
                cvm_code=1,
                issuer_code="TEST",
                trading_name="TESTE",
                sector="Bens Industriais",
                subsector="Máquinas e Equipamentos",
                segment="Máquinas e Equipamentos",
                listing_segment="Novo Mercado",
                collected_at=collected_at,
            )
        ]


def test_bootstrap_materializes_opt_in_current_sector_snapshot(tmp_path: Path) -> None:
    service = PublicDataBootstrapService(
        tmp_path,
        cvm_source=_CVMSource(),
        cvm_normalizer=_Normalizer(),
        price_source=_Prices(),
        classification_source=_Classification(),
    )
    manifest = service.run(
        PublicDataBootstrapPlan(
            start_year=2024,
            end_year=2024,
            tickers=("TEST3",),
            statements=("DRE",),
            include_current_sector_classification=True,
        ),
        collected_at=datetime(2026, 8, 29, 22, tzinfo=UTC),
        run_id="sector-test",
    )

    assert manifest.includes_current_sector_classification is True
    assert manifest.counts["sector_classifications"] == 1
    artifact_names = {artifact.name for artifact in manifest.artifacts}
    assert "b3_sector_classification_raw" in artifact_names
    assert "b3_company_catalog_raw" in artifact_names
    assert "b3_sector_classification" in artifact_names
    assert any("not point-in-time eligible" in warning for warning in manifest.warnings)

    dataset = BootstrapDataset(tmp_path / "bootstrap" / "sector-test")
    classifications = dataset.sector_classifications()
    assert len(classifications) == 1
    assert classifications[0].company_id == "cvm:1"
    assert classifications[0].point_in_time_eligible is False
