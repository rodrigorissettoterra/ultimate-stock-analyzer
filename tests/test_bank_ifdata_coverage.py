from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageProfiler
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    FinancialStatementLine,
    IssuerRecord,
    SectorClassificationRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


class FakeDataset:
    def __init__(self) -> None:
        collected = datetime(2026, 8, 29, tzinfo=UTC)
        self.manifest = SimpleNamespace(run_id="bank-coverage-test")
        self.manifest_sha256 = "a" * 64
        self._issuer = IssuerRecord(
            company_id="cvm:19348",
            cvm_code=19348,
            cnpj="60.872.504/0001-23",
            legal_name="ITAÚ UNIBANCO HOLDING S.A.",
            collected_at=collected,
        )
        self._security = SecurityRecord(
            company_id="cvm:19348",
            ticker="ITUB4",
            reference_date=date(2025, 12, 31),
            collected_at=collected,
        )
        self._classification = SectorClassificationRecord(
            company_id="cvm:19348",
            cvm_code=19348,
            cnpj="60.872.504/0001-23",
            issuer_code="ITUB",
            trading_name="ITAUUNIBANCO",
            sector="Financeiro",
            subsector="Intermediários Financeiros",
            segment="Bancos",
            collected_at=collected,
        )
        self._statement = FinancialStatementLine(
            company_id="cvm:19348",
            cvm_code=19348,
            cnpj="60.872.504/0001-23",
            company_name="ITAÚ UNIBANCO HOLDING S.A.",
            document_type="DFP",
            statement="DRE",
            consolidation_scope="DF Consolidado",
            reference_date=date(2025, 12, 31),
            fiscal_order="ÚLTIMO",
            account_code="3.11",
            account_name="Lucro Líquido",
            value_brl=1.0,
            version=1,
            collected_at=collected,
        )
        self._profile = BankPrudentialAnnualRecord(
            company_id="cvm:19348",
            cvm_code=19348,
            cnpj="60.872.504/0001-23",
            cnpj_root="60872504",
            fiscal_year=2025,
            reference_date=date(2025, 12, 31),
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
            available_from_estimate=datetime(2026, 4, 1, tzinfo=UTC),
            collected_at=collected,
            source_documents=("IFDataValores:202512:5",),
            point_in_time_eligible=False,
        )

    def issuers(self):
        return [self._issuer]

    def securities(self):
        return [self._security]

    def statements(self):
        return [self._statement]

    def sector_classifications(self):
        return [self._classification]

    def bank_profiles(self):
        return [self._profile]


def test_bank_profile_activates_specialized_contract_without_claiming_pit() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry = SectorModelRegistry.from_yaml(
        repo_root / "config/scoring/sector_registry_v0.6.yml"
    )
    dataset = FakeDataset()
    records, summary = FundamentalCoverageProfiler(
        dataset,  # type: ignore[arg-type]
        sector_registry=registry,
    ).analyze(generated_at=datetime(2026, 8, 29, tzinfo=UTC))

    assert len(records) == 1
    record = records[0]
    assert record.sector_model_id == "banks"
    assert record.applicability == "BANK_ACCOUNTING_CONTRACT_AVAILABLE"
    assert record.contract == "bank_prudential_ifdata_v1"
    assert record.critical_coverage == 1.0
    assert record.total_coverage == 1.0
    assert record.point_in_time_critical_coverage == 0.0
    assert record.longitudinal_pair_ready is False
    assert summary.bank_contract_available_company_years == 1
    assert summary.specialized_contract_required_company_years == 0


def test_verified_ifdata_subset_does_not_make_bank_structural_score_rankable() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    from ultimate_stock_analyzer.scoring.structural import (
        StructuralScoringConfig,
        StructuralScoringEngine,
    )

    engine = StructuralScoringEngine(
        StructuralScoringConfig.from_yaml(
            repo_root / "config/scoring/sectors/banks_v0.6.yml"
        )
    )
    result = engine.score_universe(
        [
            {
                "ticker": "ITUB4",
                "sector": "Financeiro",
                "peer_group": "banks",
                "roe": 0.20,
                "roa": 0.02,
                "cost_of_credit": 0.02,
                "basel_ratio": 0.16,
                "tier1_ratio": 0.14,
                "equity_to_assets": 0.10,
            }
        ]
    )[0]

    assert result.data_coverage == pytest.approx(0.45)
    assert result.rankable is False
    assert "LOW_STRUCTURAL_DATA_COVERAGE" in result.flags
