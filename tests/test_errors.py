"""Testes do formato único de erro, CORS e documentação OpenAPI."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_route_uses_error_contract(client: TestClient) -> None:
    response = client.get("/nao-existe")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"detail"}
    assert set(body["detail"]) == {"code", "message", "context"}
    assert body["detail"]["code"] == "not_found"
    assert body["detail"]["context"]["path"] == "/nao-existe"


def test_method_not_allowed_uses_error_contract(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    assert response.json()["detail"]["code"] == "method_not_allowed"


def test_corrupt_dataset_read_returns_controlled_500(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/corrompido/records")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["code"] == "dataset_read_error"
    assert body["detail"]["context"]["dataset"] == "corrompido"
    assert "Traceback" not in body["detail"]["message"]


def test_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/v1/datasets",
        headers={
            "Origin": "http://frontend.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://frontend.test"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/datasets", headers={"Origin": "http://evil.test"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_openapi_contains_contract(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/v1/datasets" in paths
    assert "/api/v1/datasets/{dataset}/records" in paths
    assert "/api/v1/datasets/{dataset}/records/{record_id}" in paths
    assert "/api/v1/datasets/{dataset}/aggregations" in paths
    assert "/api/v1/models" in paths
    assert "/api/v1/models/{name}" in paths
    assert "ErrorResponse" in schema["components"]["schemas"]

    list_records = paths["/api/v1/datasets/{dataset}/records"]["get"]
    assert "422" not in list_records["responses"]
    assert "400" in list_records["responses"]


def test_docs_and_redoc_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
