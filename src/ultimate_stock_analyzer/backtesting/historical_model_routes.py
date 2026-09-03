from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

HISTORICAL_MODEL_ROUTE_MISSING = "HISTORICAL_MODEL_ROUTE_MISSING"
HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME = "HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME"
HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE = "HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE"


class HistoricalModelRoute(BaseModel):
    """One explicit, evidence-bound model-family route for one issuer fiscal year.

    This contract intentionally stores the project model family directly rather than pretending
    to reconstruct historical B3 sector/subsector/segment labels. A route is strict-admissible only
    when its evidence contract has independently established point-in-time eligibility.
    """

    schema_version: str = "0.1"
    company_id: str
    fiscal_year: int = Field(ge=1900)
    model_id: str
    available_from: datetime
    evidence_source: str
    source_document: str
    evidence_sha256: str
    mapping_rule_version: str
    point_in_time_eligible: bool = False
    reason: str | None = None

    @field_validator(
        "company_id",
        "model_id",
        "evidence_source",
        "source_document",
        "mapping_rule_version",
    )
    @classmethod
    def _nonempty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("historical model-route text fields must be non-empty")
        return normalized

    @field_validator("available_from")
    @classmethod
    def _aware_available_from(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("historical model-route available_from must be timezone-aware")
        return value

    @field_validator("evidence_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("historical model-route evidence_sha256 must be a SHA-256 digest")
        return normalized

    @property
    def key(self) -> tuple[str, int]:
        return self.company_id, self.fiscal_year


class HistoricalModelRouteDecision(BaseModel):
    company_id: str
    fiscal_year: int
    as_of: datetime | None
    route: HistoricalModelRoute | None
    admissible: bool
    blockers: list[str]
    current_b3_fallback_used: bool = False
    effect: str = "historical_model_route_decision_no_readiness_promotion"


class HistoricalModelRouteRegistry:
    """Exact company-year registry with no implicit current-classification fallback."""

    def __init__(self, routes: list[HistoricalModelRoute] | tuple[HistoricalModelRoute, ...]) -> None:
        self._routes: dict[tuple[str, int], HistoricalModelRoute] = {}
        for route in routes:
            existing = self._routes.get(route.key)
            if existing is not None and existing != route:
                raise ValueError(
                    "conflicting historical model routes for "
                    f"{route.company_id}/{route.fiscal_year}"
                )
            self._routes[route.key] = route

    def decision(
        self,
        *,
        company_id: str,
        fiscal_year: int,
        as_of: datetime | None = None,
        require_point_in_time: bool = True,
    ) -> HistoricalModelRouteDecision:
        if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
            raise ValueError("historical model-route as_of must be timezone-aware")

        route = self._routes.get((company_id, fiscal_year))
        blockers: list[str] = []
        if route is None:
            blockers.append(HISTORICAL_MODEL_ROUTE_MISSING)
        else:
            if require_point_in_time and not route.point_in_time_eligible:
                blockers.append(HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME)
            if as_of is not None and route.available_from > as_of:
                blockers.append(HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE)

        return HistoricalModelRouteDecision(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of=as_of,
            route=route,
            admissible=route is not None and not blockers,
            blockers=blockers,
        )

    def routes(self) -> tuple[HistoricalModelRoute, ...]:
        return tuple(
            self._routes[key]
            for key in sorted(self._routes)
        )
