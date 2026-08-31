import httpx
import pytest

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


def test_cvm_download_retries_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectTimeout("TLS handshake timed out", request=request)
        return httpx.Response(200, content=b"official-data", request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    collector = CVMCollector(max_attempts=3)
    assert collector.download_registry_bytes() == b"official-data"
    assert attempts == 2


def test_cvm_download_retries_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, content=b"zip-data", request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    collector = CVMCollector(max_attempts=3)
    assert collector.download_zip("FCA", 2026) == b"zip-data"
    assert attempts == 2


def test_cvm_download_does_not_retry_non_retryable_4xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    collector = CVMCollector(max_attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        collector.download_registry_bytes()
    assert attempts == 1


def test_cvm_download_validates_retry_settings() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        CVMCollector(max_attempts=0).download_registry_bytes()
    with pytest.raises(ValueError, match="connect_timeout_seconds"):
        CVMCollector(connect_timeout_seconds=0).download_registry_bytes()
