from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    FCAApplicabilityFiling,
    FCAApplicabilityFilingLedger,
)
from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCA_MODEL_ROUTE_CONFLICT,
    FCA_MODEL_ROUTE_LEDGER_BLOCKED,
    FCA_MODEL_ROUTE_REGISTRY_MISMATCH,
    FCA_MODEL_ROUTE_SECTOR_UNMAPPED,
    FCAHistoricalModelRouteMapping,
    FCAModelRouteRule,
    materialize_fca_historical_model_routes,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

REGISTRY_PATH = Path("config/scoring/sector_registry_v0.6.yml")
SOURCE_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/"
    "fca_cia_aberta_2025.zip"
)


def _registry() -> SectorModelRegistry:
    return SectorModelRegistry.from_yaml(REGISTRY_PATH)


def _rules() -> tuple[FCAModelRouteRule, ...]:
    return (
        FCAModelRouteRule(
            sector_activity="Bancos",
            model_id="banks",
            registry_probe_source="sector_activity",
        ),
        FCAModelRouteRule(
            sector_activity="Petróleo e Gás",
            model_id="commodities",
            registry_probe_source="sector_activity",
        ),
        FCAModelRouteRule(
            sector_activity="Extração Mineral",
            model_id="commodities",
            registry_probe_source="activity_description",
        ),
    )


def _mapping(
    *,
    mappings: tuple[FCAModelRouteRule, ...] | None = None,
    sector_registry_version: str = "0.6.3",
    mapping_rule_version: str = "fca-sector-activity-v0.2",
) -> FCAHistoricalModelRouteMapping:
    return FCAHistoricalModelRouteMapping(
        mapping_rule_version=mapping_rule_version,
        sector_registry_version=sector_registry_version,
        mappings=mappings or _rules(),
        source_sha256="b" * 64,
        source_document="config/backtesting/fca_model_routes_v0.1.yml",
    )


def _filing(
    *,
    cvm_code: int = 19348,
    sector: str = "Bancos",
    activity_description: str | None = None,
    year: int = 2025,
    version: int = 1,
    document_id: int = 42,
    available_from: datetime = datetime(2025, 3, 12, tzinfo=UTC),
) -> FCAApplicabilityFiling:
    received = date.fromordinal(available_from.date().toordinal() - 1)
    return FCAApplicabilityFiling(
        cvm_code=cvm_code,
        cnpj=str(cvm_code).zfill(14),
        company_name=f"ISSUER {cvm_code}",
        reference_date=date(year, 1, 1),
        version=version,
        document_id=document_id,
        received_date=received,
        available_from=available_from,
        sector_activity=sector,
        activity_description=activity_description or sector,
        source_url=SOURCE_URL,
        archive_sha256="a" * 64,
        evidence_sha256=f"{cvm_code:064x}"[-64:],
    )


def _ledger(
    filings: list[FCAApplicabilityFiling],
    *,
    blockers: tuple[str, ...] = (),
) -> FCAApplicabilityFilingLedger:
    codes = tuple(sorted({item.cvm_code for item in filings}))
    return FCAApplicabilityFilingLedger(
        collected_at=datetime(2026, 9, 3, tzinfo=UTC),
        delivery_year=2025,
        source_url=SOURCE_URL,
        archive_sha256="a" * 64,
        archive_size_bytes=123,
        requested_cvm_codes=codes,
        root_filing_count=len(filings),
        applicability_detail_count=len(filings),
        applicability_detail_codes_observed=codes,
        missing_applicability_detail_codes=(),
        filings=tuple(filings),
        blockers=blockers,
    )


def test_mapping_targets_only_explicit_models_in_pinned_registry() -> None:
    _mapping().validate_against_registry(_registry())


def test_materializes_explicit_routes_using_source_specific_registry_probes() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[
            _ledger(
                [
                    _filing(cvm_code=19348, sector="Bancos"),
                    _filing(
                        cvm_code=9512,
                        sector="Petróleo e Gás",
                        document_id=43,
                        available_from=datetime(2025, 5, 16, tzinfo=UTC),
                    ),
                    _filing(
                        cvm_code=4170,
                        sector="Extração Mineral",
                        activity_description="Mineração",
                        document_id=44,
                        available_from=datetime(2025, 4, 12, tzinfo=UTC),
                    ),
                ]
            )
        ],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.blockers == ()
    assert result.route_count == 3
    assert {(r.company_id, r.model_id) for r in result.routes} == {
        ("cvm:19348", "banks"),
        ("cvm:9512", "commodities"),
        ("cvm:4170", "commodities"),
    }
    assert all(route.point_in_time_eligible for route in result.routes)
    vale = next(route for route in result.routes if route.company_id == "cvm:4170")
    assert "activity_description:'Mineração'" in (vale.reason or "")


def test_unmapped_sector_abstains_instead_of_using_general_default() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[_ledger([_filing(sector="Telecomunicações")])],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.routes == ()
    assert result.blocked_company_years == ("cvm:19348:2025",)
    assert result.unsupported_sector_values == ("Telecomunicações",)
    assert result.blockers == (FCA_MODEL_ROUTE_SECTOR_UNMAPPED,)


def test_registry_probe_must_select_the_configured_model() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[
            _ledger(
                [
                    _filing(
                        cvm_code=4170,
                        sector="Extração Mineral",
                        activity_description="Extração de recursos naturais",
                    )
                ]
            )
        ],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.routes == ()
    assert result.blockers == (FCA_MODEL_ROUTE_REGISTRY_MISMATCH,)
    assert result.registry_mismatch_values == (
        "Extração Mineral|activity_description|Extração de recursos naturais",
    )


def test_conflicting_model_families_for_same_company_year_fail_closed() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[
            _ledger(
                [
                    _filing(sector="Bancos", document_id=42),
                    _filing(
                        sector="Petróleo e Gás",
                        document_id=43,
                        version=2,
                        available_from=datetime(2025, 6, 1, tzinfo=UTC),
                    ),
                ]
            )
        ],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.routes == ()
    assert FCA_MODEL_ROUTE_CONFLICT in result.blockers


def test_same_model_revisions_keep_earliest_proven_availability() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[
            _ledger(
                [
                    _filing(
                        cvm_code=9512,
                        sector="Petróleo e Gás",
                        document_id=42,
                        version=1,
                        available_from=datetime(2025, 4, 2, tzinfo=UTC),
                    ),
                    _filing(
                        cvm_code=9512,
                        sector="Petróleo e Gás",
                        document_id=43,
                        version=2,
                        available_from=datetime(2025, 5, 2, tzinfo=UTC),
                    ),
                ]
            )
        ],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.blockers == ()
    assert len(result.routes) == 1
    assert result.routes[0].available_from == datetime(2025, 4, 2, tzinfo=UTC)


def test_blocked_ledger_cannot_promote_routes() -> None:
    result = materialize_fca_historical_model_routes(
        ledgers=[_ledger([_filing()], blockers=("SOURCE_BROKEN",))],
        mapping=_mapping(),
        sector_registry=_registry(),
    )
    assert result.routes == ()
    assert FCA_MODEL_ROUTE_LEDGER_BLOCKED in result.blockers


def test_mapping_registry_version_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="registry version mismatch"):
        _mapping(sector_registry_version="0.0.0").validate_against_registry(_registry())


def test_mapping_cannot_target_default_or_unknown_model() -> None:
    default_rule = (
        FCAModelRouteRule(
            sector_activity="Unknown Sector",
            model_id="general_corporate",
            registry_probe_source="sector_activity",
        ),
    )
    with pytest.raises(ValueError, match="not an explicit sector model"):
        _mapping(mappings=default_rule).validate_against_registry(_registry())


def test_mapping_rejects_duplicate_sector_labels() -> None:
    duplicate_rules = (
        FCAModelRouteRule(
            sector_activity="Bancos",
            model_id="banks",
            registry_probe_source="sector_activity",
        ),
        FCAModelRouteRule(
            sector_activity="Bancos",
            model_id="commodities",
            registry_probe_source="sector_activity",
        ),
    )
    with pytest.raises(ValidationError, match="duplicate sector labels"):
        _mapping(mappings=duplicate_rules)


def test_mapping_rules_are_deeply_immutable() -> None:
    mapping = _mapping()
    with pytest.raises(ValidationError, match="frozen"):
        mapping.mappings[0].model_id = "commodities"


def test_mapping_rule_changes_route_evidence_hash() -> None:
    ledger = _ledger([_filing()])
    first = materialize_fca_historical_model_routes(
        ledgers=[ledger], mapping=_mapping(), sector_registry=_registry()
    )
    second = materialize_fca_historical_model_routes(
        ledgers=[ledger],
        mapping=_mapping(mapping_rule_version="fca-sector-activity-v0.3"),
        sector_registry=_registry(),
    )
    assert first.routes[0].evidence_sha256 != second.routes[0].evidence_sha256
