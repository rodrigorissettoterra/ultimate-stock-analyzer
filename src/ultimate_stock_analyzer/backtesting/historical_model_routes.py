from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

HISTORICAL_MODEL_ROUTE_MISSING = "HISTORICAL_MODEL_ROUTE_MISSING"
HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME = "HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME"
HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE = "HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE"

_CANONICAL_COMPANY_ID = re.compile(r"^cvm:[1-9]\d*$")


def _canonical_company_id(value: str) -> str:
    normalized = value.strip()
    if not _CANONICAL_COMPANY_ID.fullmatch(normalized):
        raise ValueError("historical model-route company_id must be canonical cvm:<CD_CVM>")
    return normalized


class HistoricalModelRoute(BaseModel):
    """Immutable, evidence-bound model-family route for one issuer fiscal year."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "0.2"
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

    @field_validator("company_id")
    @classmethod
    def _company_id(cls, value: str) -> str:
        return _canonical_company_id(value)

    @field_validator(
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
    model_config = ConfigDict(frozen=True)

    company_id: str
    fiscal_year: int
    as_of: datetime | None
    route: HistoricalModelRoute | None
    admissible: bool
    blockers: tuple[str, ...]
    current_b3_fallback_used: bool = False
    effect: str = "historical_model_route_decision_no_readiness_promotion"


class HistoricalModelRouteRegistry:
    """Exact company-year registry with immutable routes and no current-B3 fallback."""

    def __init__(
        self,
        routes: list[HistoricalModelRoute] | tuple[HistoricalModelRoute, ...],
    ) -> None:
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
        canonical_company_id = _canonical_company_id(company_id)
        if require_point_in_time and as_of is None:
            raise ValueError(
                "historical model-route strict decisions require a timezone-aware as_of"
            )
        if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
            raise ValueError("historical model-route as_of must be timezone-aware")

        route = self._routes.get((canonical_company_id, fiscal_year))
        blockers: list[str] = []
        if route is None:
            blockers.append(HISTORICAL_MODEL_ROUTE_MISSING)
        else:
            if require_point_in_time and not route.point_in_time_eligible:
                blockers.append(HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME)
            if as_of is not None and route.available_from > as_of:
                blockers.append(HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE)

        return HistoricalModelRouteDecision(
            company_id=canonical_company_id,
            fiscal_year=fiscal_year,
            as_of=as_of,
            route=route,
            admissible=route is not None and not blockers,
            blockers=tuple(blockers),
        )

    def routes(self) -> tuple[HistoricalModelRoute, ...]:
        return tuple(self._routes[key] for key in sorted(self._routes))
