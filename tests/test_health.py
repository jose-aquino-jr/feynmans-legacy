"""Testes de health check e descoberta básica."""

from __future__ import annotations

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Feynman's Legacy API"
    assert body["environment"] == "test"
    assert body["data_dir_exists"] is True
    assert body["models_dir_exists"] is True
    assert body["uptime_seconds"] >= 0
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_health_with_missing_data_dirs(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "sem_dados",
        models_dir=tmp_path / "sem_modelos",
    )
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health")
        datasets = test_client.get("/api/v1/datasets")
        models = test_client.get("/api/v1/models")

    assert response.status_code == 200
    assert response.json()["data_dir_exists"] is False
    assert response.json()["models_dir_exists"] is False
    assert datasets.status_code == 200
    assert datasets.json() == {"items": [], "total": 0}
    assert models.status_code == 200
    assert models.json() == {"items": [], "total": 0}


def test_root_lists_entrypoints(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
    assert response.json()["datasets"] == "/api/v1/datasets"
