"""Testes de listagem/metadados de datasets."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _by_name(payload: dict) -> dict[str, dict]:
    return {item["name"]: item for item in payload["items"]}


def test_list_datasets_reflects_files(client: TestClient) -> None:
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    body = response.json()
    items = _by_name(body)
    assert body["total"] == len(items)
    assert {
        "locais",
        "clusters",
        "case1/ranking",
        "vazio",
        "corrompido",
    }.issubset(items)
    assert "notas" not in items

    locais = items["locais"]
    assert locais["format"] == "csv"
    assert locais["row_count"] == 6
    assert locais["description"] == "Análogos terrestres de referência."
    assert locais["id_column"] == "id"
    assert locais["tags"] == ["análogos", "terrestres"]
    assert locais["metadata"]["source"] == "ETL"
    assert locais["readable"] is True
    assert locais["error"] is None
    assert {column["name"] for column in locais["columns"]} >= {
        "id",
        "nome",
        "clima",
        "score",
    }
    score = next(column for column in locais["columns"] if column["name"] == "score")
    assert score["description"] == "Similaridade entre 0 e 1."

    clusters = items["clusters"]
    assert clusters["format"] == "parquet"
    assert clusters["row_count"] == 3
    assert clusters["readable"] is True

    vazio = items["vazio"]
    assert vazio["row_count"] == 0

    corrupted = items["corrompido"]
    assert corrupted["readable"] is False
    assert corrupted["row_count"] is None
    assert "ilegível" in corrupted["error"]


def test_get_dataset_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "locais"
    assert body["file"] == "locais.csv"
    assert body["row_count"] == 6


def test_get_nested_dataset_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/case1/ranking")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "case1/ranking"
    assert body["file"] == "case1/ranking.csv"
    assert body["row_count"] == 2


def test_get_missing_dataset_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/nao_existe")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "dataset_not_found"
    assert "nao_existe" in detail["message"]
    assert detail["context"]["dataset"] == "nao_existe"
