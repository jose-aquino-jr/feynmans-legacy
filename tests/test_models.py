"""Testes dos metadados de artefatos de modelo."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_models(client: TestClient) -> None:
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    by_name = {item["name"]: item for item in body["items"]}
    assert set(by_name) == {"cluster_kmeans", "previsao/xgboost"}

    kmeans = by_name["cluster_kmeans"]
    assert kmeans["format"] == "joblib"
    assert kmeans["description"] == "KMeans dos análogos terrestres."
    assert kmeans["algorithm"] == "KMeans"
    assert kmeans["framework"] == "scikit-learn"
    assert kmeans["target"] == "cluster"
    assert kmeans["trained_at"] == "2026-11-01"
    assert kmeans["metrics"] == {"silhouette": 0.42}
    assert kmeans["params"] == {"n_clusters": 4}
    assert kmeans["tags"] == ["clusterização"]
    assert kmeans["size_bytes"] > 0


def test_get_model(client: TestClient) -> None:
    response = client.get("/api/v1/models/previsao/xgboost")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "previsao/xgboost"
    assert body["file"] == "previsao/xgboost.ubj"
    assert body["format"] == "ubj"


def test_get_model_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/models/nao_existe")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "model_not_found"
    assert detail["context"]["model"] == "nao_existe"
