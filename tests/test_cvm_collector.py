from ultimate_stock_analyzer.collectors.cvm import CVMCollector


def test_cvm_urls_cover_registry_and_structured_documents() -> None:
    collector = CVMCollector()

    assert collector.dataset_url("DFP", 2025).endswith(
        "/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"
    )
    assert collector.dataset_url("ITR", 2026).endswith(
        "/DOC/ITR/DADOS/itr_cia_aberta_2026.zip"
    )
    assert collector.dataset_url("FCA", 2026).endswith(
        "/DOC/FCA/DADOS/fca_cia_aberta_2026.zip"
    )
    assert collector.registry_url().endswith("/CAD/DADOS/cad_cia_aberta.csv")
