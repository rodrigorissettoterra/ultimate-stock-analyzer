from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    FCAApplicabilityFiling,
    FCAApplicabilityFilingLedger,
)
from ultimate_stock_analyzer.backtesting.historical_model_routes import HistoricalModelRoute
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

FCA_MODEL_ROUTE_LEDGER_BLOCKED = "FCA_MODEL_ROUTE_LEDGER_BLOCKED"
FCA_MODEL_ROUTE_SECTOR_UNMAPPED = "FCA_MODEL_ROUTE_SECTOR_UNMAPPED"
FCA_MODEL_ROUTE_REGISTRY_MISMATCH = "FCA_MODEL_ROUTE_REGISTRY_MISMATCH"
FCA_MODEL_ROUTE_CONFLICT = "FCA_MODEL_ROUTE_CONFLICT"
FCA_MODEL_ROUTE_NOT_POINT_IN_TIME = "FCA_MODEL_ROUTE_NOT_POINT_IN_TIME"

ProbeSource = Literal["sector_activity", "activity_description"]


class FCAModelRouteRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sector_activity: str
    model_id: str
    registry_probe_source: ProbeSource

    @field_validator("sector_activity", "model_id")
    @classmethod
    def _exact_nonempty(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("FCA model-route rule values must be exact non-empty trimmed strings")
        return value

    def probe_value(self, filing: FCAApplicabilityFiling) -> str:
        if self.registry_probe_source == "sector_activity":
            return filing.sector_activity
        return filing.activity_description


class FCAHistoricalModelRouteMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "0.2"
    mapping_rule_version: str
    sector_registry_version: str
    mappings: tuple[FCAModelRouteRule, ...]
    source_sha256: str
    source_document: str

    @field_validator("mapping_rule_version", "sector_registry_version", "source_document")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("FCA model-route mapping metadata must be non-empty and trimmed")
        return value

    @field_validator("mappings")
    @classmethod
    def _nonempty_mappings(
        cls, value: tuple[FCAModelRouteRule, ...]
    ) -> tuple[FCAModelRouteRule, ...]:
        if not value:
            raise ValueError("FCA model-route mappings must not be empty")
        return value

    @field_validator("source_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        normalized = value.lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("FCA mapping source_sha256 must be a SHA-256 digest")
        return normalized

    @model_validator(mode="after")
    def _unique_sector_labels(self) -> Self:
        labels = [rule.sector_activity for rule in self.mappings]
        if len(labels) != len(set(labels)):
            raise ValueError("FCA model-route mapping contains duplicate sector labels")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> FCAHistoricalModelRouteMapping:
        source_path = Path(path)
        return cls.from_yaml_bytes(
            source_path.read_bytes(),
            source_document=source_path.as_posix(),
        )

    @classmethod
    def from_yaml_bytes(
        cls,
        content: bytes,
        *,
        source_document: str,
    ) -> FCAHistoricalModelRouteMapping:
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("FCA model-route mapping must be UTF-8") from exc
        payload = yaml.safe_load(decoded)
        if not isinstance(payload, dict):
            raise TypeError("FCA model-route mapping YAML must contain an object")
        return cls(
            **payload,
            source_sha256=hashlib.sha256(content).hexdigest(),
            source_document=source_document,
        )

    def rule_for_sector(self, sector_activity: str) -> FCAModelRouteRule | None:
        for rule in self.mappings:
            if rule.sector_activity == sector_activity:
                return rule
        return None

    def validate_against_registry(self, registry: SectorModelRegistry) -> None:
        if registry.version != self.sector_registry_version:
            raise ValueError(
                "FCA model-route mapping sector registry version mismatch: "
                f"mapping={self.sector_registry_version} registry={registry.version}"
            )
        allowed_model_ids = {model.model_id for model in registry.models}
        for rule in self.mappings:
            if rule.model_id not in allowed_model_ids:
                raise ValueError(
                    "FCA model-route mapping target is not an explicit sector model: "
                    f"sector={rule.sector_activity!r} model={rule.model_id!r}"
                )


class FCAHistoricalModelRouteMaterialization(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "0.2"
    mapping_rule_version: str
    mapping_source_document: str
    mapping_source_sha256: str
    sector_registry_version: str
    route_count: int = Field(ge=0)
    routes: tuple[HistoricalModelRoute, ...]
    blocked_company_years: tuple[str, ...]
    unsupported_sector_values: tuple[str, ...]
    registry_mismatch_values: tuple[str, ...]
    blockers: tuple[str, ...]
    readiness_promotion_allowed: bool = False
    effect: str = "fca_historical_model_routes_materialized_no_readiness_promotion"


def materialize_fca_historical_model_routes(
    *,
    ledgers: list[FCAApplicabilityFilingLedger] | tuple[FCAApplicabilityFilingLedger, ...],
    mapping: FCAHistoricalModelRouteMapping,
    sector_registry: SectorModelRegistry,
) -> FCAHistoricalModelRouteMaterialization:
    """Materialize explicit PIT model routes from exact FCA filing evidence."""
    mapping.validate_against_registry(sector_registry)

    grouped: dict[tuple[int, int], list[FCAApplicabilityFiling]] = defaultdict(list)
    blockers: set[str] = set()
    blocked_keys: set[tuple[int, int]] = set()
    unsupported_sectors: set[str] = set()
    registry_mismatches: set[str] = set()

    for ledger in ledgers:
        if ledger.blockers:
            blockers.add(FCA_MODEL_ROUTE_LEDGER_BLOCKED)
            for filing in ledger.filings:
                blocked_keys.add((filing.cvm_code, filing.reference_date.year))
            continue
        for filing in ledger.filings:
            grouped[(filing.cvm_code, filing.reference_date.year)].append(filing)

    routes: list[HistoricalModelRoute] = []
    for key, filings in sorted(grouped.items()):
        mapped: list[tuple[FCAApplicabilityFiling, FCAModelRouteRule, str]] = []
        key_blocked = False
        for filing in filings:
            if not (
                filing.exact_document_join
                and filing.issuer_identity_match
                and filing.reference_date_match
                and filing.point_in_time_eligible_from_available_from
            ):
                blockers.add(FCA_MODEL_ROUTE_NOT_POINT_IN_TIME)
                key_blocked = True
                continue

            rule = mapping.rule_for_sector(filing.sector_activity)
            if rule is None:
                blockers.add(FCA_MODEL_ROUTE_SECTOR_UNMAPPED)
                unsupported_sectors.add(filing.sector_activity)
                key_blocked = True
                continue

            probe_value = rule.probe_value(filing)
            selection = sector_registry.select({"sector": probe_value})
            if selection.is_fallback or selection.model_id != rule.model_id:
                blockers.add(FCA_MODEL_ROUTE_REGISTRY_MISMATCH)
                registry_mismatches.add(
                    f"{filing.sector_activity}|{rule.registry_probe_source}|{probe_value}"
                )
                key_blocked = True
                continue
            mapped.append((filing, rule, probe_value))

        if key_blocked or not mapped:
            blocked_keys.add(key)
            continue

        model_ids = {rule.model_id for _filing, rule, _probe in mapped}
        if len(model_ids) != 1:
            blockers.add(FCA_MODEL_ROUTE_CONFLICT)
            blocked_keys.add(key)
            continue

        filing, rule, probe_value = min(mapped, key=lambda item: item[0].available_from)
        route_evidence = _route_evidence_sha256(
            filing=filing,
            rule=rule,
            probe_value=probe_value,
            mapping=mapping,
        )
        routes.append(
            HistoricalModelRoute(
                company_id=f"cvm:{filing.cvm_code}",
                fiscal_year=filing.reference_date.year,
                model_id=rule.model_id,
                available_from=filing.available_from,
                evidence_source="CVM_FCA",
                source_document=(
                    f"{filing.source_url}#ID_Documento={filing.document_id}:"
                    f"Versao={filing.version}"
                ),
                evidence_sha256=route_evidence,
                mapping_rule_version=(
                    f"{mapping.mapping_rule_version}+sector-registry/"
                    f"{sector_registry.version}"
                ),
                point_in_time_eligible=True,
                reason=(
                    f"CVM FCA Setor_Atividade={filing.sector_activity!r}; "
                    f"registry_probe={rule.registry_probe_source}:{probe_value!r}"
                ),
            )
        )

    ordered_routes = tuple(sorted(routes, key=lambda item: (item.company_id, item.fiscal_year)))
    return FCAHistoricalModelRouteMaterialization(
        mapping_rule_version=mapping.mapping_rule_version,
        mapping_source_document=mapping.source_document,
        mapping_source_sha256=mapping.source_sha256,
        sector_registry_version=sector_registry.version,
        route_count=len(ordered_routes),
        routes=ordered_routes,
        blocked_company_years=tuple(
            f"cvm:{code}:{year}" for code, year in sorted(blocked_keys)
        ),
        unsupported_sector_values=tuple(sorted(unsupported_sectors)),
        registry_mismatch_values=tuple(sorted(registry_mismatches)),
        blockers=tuple(sorted(blockers)),
    )


def _route_evidence_sha256(
    *,
    filing: FCAApplicabilityFiling,
    rule: FCAModelRouteRule,
    probe_value: str,
    mapping: FCAHistoricalModelRouteMapping,
) -> str:
    payload: dict[str, Any] = {
        "filing_evidence_sha256": filing.evidence_sha256,
        "mapping_source_sha256": mapping.source_sha256,
        "mapping_rule_version": mapping.mapping_rule_version,
        "sector_registry_version": mapping.sector_registry_version,
        "sector_activity": filing.sector_activity,
        "registry_probe_source": rule.registry_probe_source,
        "registry_probe_value": probe_value,
        "model_id": rule.model_id,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
