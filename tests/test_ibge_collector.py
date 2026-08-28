import pytest

from ultimate_stock_analyzer.collectors.ibge import SIDRACollector


def test_sidra_collector_builds_only_relative_official_query_paths() -> None:
    collector = SIDRACollector()
    url = collector.build_url("t/7060/n1/all/v/63/p/last 12")
    assert url.startswith("https://apisidra.ibge.gov.br/values/")
    with pytest.raises(ValueError):
        collector.build_url("https://example.com/values/t/1")
