from fastapi.testclient import TestClient

from ultimate_stock_analyzer.api.main import create_app


def test_dashboard_is_served_by_the_api() -> None:
    client = TestClient(create_app())
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "Ultimate Stock Analyzer" in response.text
    assert "/v1/ranking" not in response.text


def test_dashboard_static_assets_are_available() -> None:
    client = TestClient(create_app())
    css = client.get("/dashboard/styles.css")
    javascript = client.get("/dashboard/app.js")
    assert css.status_code == 200
    assert javascript.status_code == 200
    assert "loadRanking" in javascript.text
