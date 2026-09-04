from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.scoring.structural import (
    StructuralScoreResult,
    StructuralScoringConfig,
    StructuralScoringEngine,
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold().strip()


def _normalize_company_id(value: Any) -> str:
    return str(value or "").strip().casefold()


@dataclass(frozen=True, slots=True)
class SectorModelDefinition:
    model_id: str
    config_path: Path
    priority: int = 0
    company_ids: tuple[str, ...] = ()
    sector_contains: tuple[str, ...] = ()
    subsector_contains: tuple[str, ...] = ()
    segment_contains: tuple[str, ...] = ()
    industry_contains: tuple[str, ...] = ()
    peer_group_by: tuple[str, ...] = ()

    def match_reason(self, row: dict[str, Any]) -> str | None:
        company_id = _normalize_company_id(row.get("company_id"))
        if company_id:
            for configured_company_id in self.company_ids:
                if company_id == _normalize_company_id(configured_company_id):
                    return f"company_id:{company_id}"

        fields = (
            ("sector", self.sector_contains),
            ("subsector", self.subsector_contains),
            ("segment", self.segment_contains),
            ("industry", self.industry_contains),
        )
        for field_name, patterns in fields:
            value = _normalize_text(row.get(field_name))
            if not value:
                continue
            for raw_pattern in patterns:
                pattern = _normalize_text(raw_pattern)
                if pattern and pattern in value:
                    return f"{field_name}:{pattern}"
        return None

    def peer_group(self, row: dict[str, Any]) -> str:
        for field_name in self.peer_group_by:
            value = str(row.get(field_name) or "").strip()
            if value:
                return value
        return self.model_id


@dataclass(frozen=True, slots=True)
class SectorModelSelection:
    model_id: str
    config_path: Path
    reason: str
    is_fallback: bool
    peer_group: str


class SectorModelRegistry:
    def __init__(
        self,
        *,
        version: str,
        default_model: SectorModelDefinition,
        models: tuple[SectorModelDefinition, ...],
    ) -> None:
        self.version = version
        self.default_model = default_model
        self.models = tuple(sorted(models, key=lambda item: item.priority, reverse=True))
        ids = [default_model.model_id, *(model.model_id for model in self.models)]
        if len(ids) != len(set(ids)):
            raise ValueError("sector model ids must be unique")

    @classmethod
    def from_yaml(cls, path: str | Path) -> SectorModelRegistry:
        registry_path = Path(path)
        return cls.from_yaml_bytes(
            registry_path.read_bytes(),
            base_dir=registry_path.parent,
        )

    @classmethod
    def from_yaml_bytes(
        cls,
        content: bytes,
        *,
        base_dir: str | Path,
    ) -> SectorModelRegistry:
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("sector model registry must be UTF-8") from exc
        raw = yaml.safe_load(decoded)
        if not isinstance(raw, dict):
            raise TypeError("sector model registry YAML must contain an object")

        resolved_base_dir = Path(base_dir)
        default_raw = raw["default_model"]
        if not isinstance(default_raw, dict):
            raise TypeError("sector model registry default_model must contain an object")
        default_model = _definition_from_raw(default_raw, resolved_base_dir)

        models_raw = raw.get("models", [])
        if not isinstance(models_raw, list):
            raise TypeError("sector model registry models must contain a list")
        models = tuple(
            _definition_from_raw(model_raw, resolved_base_dir)
            for model_raw in models_raw
        )
        return cls(
            version=str(raw["version"]),
            default_model=default_model,
            models=models,
        )

    def select(self, row: dict[str, Any]) -> SectorModelSelection:
        for model in self.models:
            reason = model.match_reason(row)
            if reason is not None:
                return SectorModelSelection(
                    model_id=model.model_id,
                    config_path=model.config_path,
                    reason=reason,
                    is_fallback=False,
                    peer_group=model.peer_group(row),
                )
        return SectorModelSelection(
            model_id=self.default_model.model_id,
            config_path=self.default_model.config_path,
            reason="default_fallback",
            is_fallback=True,
            peer_group=self.default_model.peer_group(row),
        )


def _definition_from_raw(raw: dict[str, Any], base_dir: Path) -> SectorModelDefinition:
    match = raw.get("match") or {}
    company_ids = tuple(str(item).strip().casefold() for item in match.get("company_ids", []))
    for company_id in company_ids:
        if not company_id.startswith("cvm:"):
            raise ValueError(
                "sector model company_ids must use canonical cvm:<CD_CVM> identity: "
                f"model={raw['id']} company_id={company_id}"
            )
        try:
            int(company_id.split(":", 1)[1])
        except ValueError as exc:
            raise ValueError(
                "invalid canonical sector model company_id: "
                f"model={raw['id']} company_id={company_id}"
            ) from exc
    if len(company_ids) != len(set(company_ids)):
        raise ValueError(f"duplicate sector model company_ids: model={raw['id']}")

    config_path = (base_dir / str(raw["config"])).resolve()
    return SectorModelDefinition(
        model_id=str(raw["id"]),
        config_path=config_path,
        priority=int(raw.get("priority", 0)),
        company_ids=company_ids,
        sector_contains=tuple(str(item) for item in match.get("sector_contains", [])),
        subsector_contains=tuple(
            str(item) for item in match.get("subsector_contains", [])
        ),
        segment_contains=tuple(str(item) for item in match.get("segment_contains", [])),
        industry_contains=tuple(
            str(item) for item in match.get("industry_contains", [])
        ),
        peer_group_by=tuple(str(item) for item in raw.get("peer_group_by", [])),
    )


class SectorStructuralScoringEngine:
    """Route each issuer to a sector-specific structural model before scoring."""

    def __init__(self, registry: SectorModelRegistry) -> None:
        self.registry = registry
        self._config_cache: dict[Path, StructuralScoringConfig] = {}

    def _config(self, path: Path) -> StructuralScoringConfig:
        if path not in self._config_cache:
            self._config_cache[path] = StructuralScoringConfig.from_yaml(path)
        return self._config_cache[path]

    def score_universe(self, rows: list[dict[str, Any]]) -> list[StructuralScoreResult]:
        selections: dict[str, SectorModelSelection] = {}
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in rows:
            ticker = str(row["ticker"])
            if ticker in selections:
                raise ValueError(f"duplicate ticker in sector scoring universe: {ticker}")
            selection = self.registry.select(row)
            selections[ticker] = selection
            routed = dict(row)
            routed["peer_group"] = selection.peer_group
            grouped[selection.model_id].append(routed)

        results: list[StructuralScoreResult] = []
        for model_id, model_rows in grouped.items():
            first_ticker = str(model_rows[0]["ticker"])
            selection = selections[first_ticker]
            config = self._config(selection.config_path)
            engine = StructuralScoringEngine(config)
            for result in engine.score_universe(model_rows):
                selected = selections[result.ticker]
                results.append(
                    replace(
                        result,
                        model_id=model_id,
                        model_family=config.model_family,
                        selection_reason=selected.reason,
                    )
                )

        return sorted(
            results,
            key=lambda result: (
                result.rankable,
                result.structural_score,
                result.confidence,
            ),
            reverse=True,
        )

    def rank_universe(self, rows: list[dict[str, Any]]) -> list[StructuralScoreResult]:
        return [result for result in self.score_universe(rows) if result.rankable]
