from __future__ import annotations

from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCAHistoricalModelRouteMapping,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "config/backtesting/fca_model_routes_v0.2.yml"
REGISTRY_PATH = REPO_ROOT / "config/scoring/sector_registry_v0.6.yml"


def test_fca_mapping_from_verified_bytes_matches_path_loader() -> None:
    by_path = FCAHistoricalModelRouteMapping.from_yaml(MAPPING_PATH)
    by_bytes = FCAHistoricalModelRouteMapping.from_yaml_bytes(
        MAPPING_PATH.read_bytes(),
        source_document=MAPPING_PATH.as_posix(),
    )

    assert by_bytes == by_path


def test_sector_registry_from_verified_bytes_matches_path_loader() -> None:
    by_path = SectorModelRegistry.from_yaml(REGISTRY_PATH)
    by_bytes = SectorModelRegistry.from_yaml_bytes(
        REGISTRY_PATH.read_bytes(),
        base_dir=REGISTRY_PATH.parent,
    )

    assert by_bytes.version == by_path.version
    assert by_bytes.default_model == by_path.default_model
    assert by_bytes.models == by_path.models

    probes = (
        {"sector": "Bancos"},
        {"sector": "Petróleo"},
        {"sector": "Energia Elétrica"},
        {"company_id": "cvm:7617"},
        {"sector": "Indústria"},
    )
    for probe in probes:
        assert by_bytes.select(probe) == by_path.select(probe)
