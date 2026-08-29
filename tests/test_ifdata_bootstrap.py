from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.bootstrap import (
    BootstrapDataset,
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.collectors.bcb_ifdata import (
    IFDataAnnualCollection,
    IFDataRawPayload,
)
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


class FakeCVMSource:
    def download_registry_bytes(self) -> bytes:
        return b"registry"

    def download_zip(self, document: str, year: int) -> bytes:
        return f"{document}-{year}".encode()


class FakeCVMNormalizer:
    def load_issuer_master_from_bytes(
        self,
        content: bytes,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        assert content == b"registry"
        assert active_only is False
        return [
            IssuerRecord(
                company_id="cvm:19348",
                cvm_code=19348,
                cnpj="60.872.504/0001-23",
                legal_name="ITAÚ UNIBANCO HOLDING S.A.",
                collected_at=collected_at,
            )
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
                company_id="cvm:19348",
                ticker="ITUB4",
                reference_date=date(year, 12, 31),
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
        year = int(archive.decode().split("-")[1])
        return [
            FinancialStatementLine(
                company_id="cvm:19348",
                cvm_code=19348,
                cnpj="60.872.504/0001-23",
                company_name="ITAÚ UNIBANCO HOLDING S.A.",
                document_type=document_type,
                statement="DRE",
                consolidation_scope="DF Consolidado",
                reference_date=date(year, 12, 31),
                fiscal_order="ÚLTIMO",
                account_code="3.11",
                account_name="Lucro Líquido",
                value_brl=1.0,
                version=1,
                collected_at=collected_at,
            )
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
        return [
            PriceBar(
                ticker="ITUB4",
                trade_date=date(year, 12, 30),
                open=30.0,
                high=31.0,
                low=29.0,
                close=30.5,
                volume=1_000_000.0,
                trades=100,
                quantity=10_000,
            )
        ]


class FakeIFDataSource:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def collect_annual_bank_profiles(
        self,
        issuers: list[IssuerRecord],
        *,
        fiscal_year: int,
        collected_at: datetime,
    ) -> IFDataAnnualCollection:
        self.calls.append(fiscal_year)
        assert len(issuers) == 1
        profile = BankPrudentialAnnualRecord(
            company_id=issuers[0].company_id,
            cvm_code=issuers[0].cvm_code,
            cnpj=issuers[0].cnpj,
            cnpj_root="60872504",
            fiscal_year=fiscal_year,
            reference_date=date(fiscal_year, 12, 31),
            ifdata_cod_inst="C0080099",
            ifdata_name="ITAU - PRUDENCIAL",
            total_assets=2_400.0,
            prior_total_assets=2_000.0,
            equity=240.0,
            prior_equity=200.0,
            gross_credit_portfolio=1_100.0,
            prior_gross_credit_portfolio=900.0,
            annual_net_income=44.0,
            annual_credit_loss_result=-20.0,
            basel_ratio=0.16,
            tier1_ratio=0.14,
            core_equity_tier1_ratio=0.12,
            leverage_ratio=0.07,
            roe=0.20,
            roa=0.02,
            cost_of_credit=0.02,
            equity_to_assets=0.10,
            available_from_estimate=datetime(fiscal_year + 1, 4, 1, tzinfo=UTC),
            collected_at=collected_at,
            source_documents=(f"IFDataValores:{fiscal_year}12:5",),
            point_in_time_eligible=False,
        )
        return IFDataAnnualCollection(
            fiscal_year=fiscal_year,
            profiles=(profile,),
            raw_payloads=(
                IFDataRawPayload(
                    ano_mes=fiscal_year * 100 + 12,
                    kind="cadastro",
                    content=b'{"value":[]}',
                ),
                IFDataRawPayload(
                    ano_mes=fiscal_year * 100 + 12,
                    kind="report",
                    report_number="5",
                    content=b'{"value":[]}',
                ),
            ),
        )


def test_bootstrap_materializes_ifdata_raw_and_normalized_profile(tmp_path: Path) -> None:
    ifdata = FakeIFDataSource()
    service = PublicDataBootstrapService(
        tmp_path,
        cvm_source=FakeCVMSource(),
        cvm_normalizer=FakeCVMNormalizer(),
        price_source=FakePriceSource(),
        ifdata_source=ifdata,
    )
    manifest = service.run(
        PublicDataBootstrapPlan(
            start_year=2025,
            end_year=2025,
            tickers=("ITUB4",),
            statements=("DRE",),
            include_bank_ifdata=True,
        ),
        collected_at=datetime(2026, 8, 29, tzinfo=UTC),
        run_id="ifdata-bootstrap",
    )

    assert manifest.status == "COMPLETE"
    assert manifest.includes_bank_ifdata is True
    assert manifest.counts["bank_prudential_profiles"] == 1
    assert ifdata.calls == [2025]

    run_dir = tmp_path / "bootstrap" / "ifdata-bootstrap"
    assert (
        run_dir / "raw/bcb/ifdata/2025/202512_cadastro.json"
    ).read_bytes() == b'{"value":[]}'
    assert (
        run_dir / "raw/bcb/ifdata/2025/202512_report_5.json"
    ).read_bytes() == b'{"value":[]}'

    dataset = BootstrapDataset(run_dir)
    profiles = dataset.bank_profiles()
    assert len(profiles) == 1
    assert profiles[0].ifdata_cod_inst == "C0080099"
    assert profiles[0].point_in_time_eligible is False
