from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HISTORICAL_MODEL_ROUTE_MISSING,
    HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME,
    HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE,
    HistoricalModelRoute,
    HistoricalModelRouteRegistry,
)

AVAILABLE = datetime(2025, 5, 2, tzinfo=UTC)


def _route(
    *,
    company_id: str = "cvm:19348",
    fiscal_year: int = 2024,
    model_id: str = "banks",
    point_in_time_eligible: bool = True,
    available_from: datetime = AVAILABLE,
) -> HistoricalModelRoute:
    return HistoricalModelRoute(
        company_id=company_id,
        fiscal_year=fiscal_year,
        model_id=model_id,
        available_from=available_from,
        evidence_source="CVM_FCA",
        source_document="fca_cia_aberta_2025.zip#fca_cia_aberta_geral",
        evidence_sha256="a" * 64,
        mapping_rule_version="historical-model-route-v1",
        point_in_time_eligible=point_in_time_eligible,
        reason="explicit historical model-family evidence",
    )


def test_exact_point_in_time_company_year_route_is_admissible() -> None:
    registry = HistoricalModelRouteRegistry([_route()])
    decision = registry.decision(
        company_id="cvm:19348",
        fiscal_year=2024,
        as_of=datetime(2025, 6, 1, tzinfo=UTC),
    )
    assert decision.admissible
    assert decision.route is not None
    assert decision.route.model_id == "banks"
    assert decision.blockers == []
    assert not decision.current_b3_fallback_used


def test_route_does_not_spill_into_adjacent_fiscal_year() -> None:
    registry = HistoricalModelRouteRegistry([_route(fiscal_year=2024)])
    decision = registry.decision(
        company_id="cvm:19348",
        fiscal_year=2025,
        as_of=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert not decision.admissible
    assert decision.route is None
    assert decision.blockers == [HISTORICAL_MODEL_ROUTE_MISSING]
    assert not decision.current_b3_fallback_used


def test_non_point_in_time_route_remains_diagnostic_only() -> None:
    registry = HistoricalModelRouteRegistry([_route(point_in_time_eligible=False)])
    strict = registry.decision(
        company_id="cvm:19348",
        fiscal_year=2024,
        as_of=datetime(2025, 6, 1, tzinfo=UTC),
    )
    diagnostic = registry.decision(
        company_id="cvm:19348",
        fiscal_year=2024,
        require_point_in_time=False,
    )
    assert not strict.admissible
    assert strict.blockers == [HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME]
    assert diagnostic.admissible
    assert diagnostic.blockers == []


def test_route_cannot_be_used_before_its_evidence_was_available() -> None:
    registry = HistoricalModelRouteRegistry([_route()])
    decision = registry.decision(
        company_id="cvm:19348",
        fiscal_year=2024,
        as_of=datetime(2025, 4, 30, tzinfo=UTC),
    )
    assert not decision.admissible
    assert decision.blockers == [HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE]


def test_strict_decision_requires_as_of_to_prevent_lookahead() -> None:
    registry = HistoricalModelRouteRegistry([_route()])
    with pytest.raises(ValueError, match="strict decisions require"):
        registry.decision(company_id="cvm:19348", fiscal_year=2024)


def test_conflicting_duplicate_company_year_routes_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting historical model routes"):
        HistoricalModelRouteRegistry(
            [_route(model_id="banks"), _route(model_id="general_corporate")]
        )


def test_naive_availability_and_as_of_are_rejected() -> None:
    naive_available = datetime(2025, 5, 2, tzinfo=UTC).replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        _route(available_from=naive_available)

    registry = HistoricalModelRouteRegistry([_route()])
    naive_as_of = datetime(2025, 6, 1, tzinfo=UTC).replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        registry.decision(
            company_id="cvm:19348",
            fiscal_year=2024,
            as_of=naive_as_of,
        )
