"""Testes do contrato de registros: paginação, filtros, ordenação e projeção."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_records_default_pagination(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "locais"
    assert body["total"] == 6
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert len(body["items"]) == 6


def test_records_pagination(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records?limit=2&offset=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert [item["id"] for item in body["items"]] == [3, 4]


def test_records_offset_beyond_total_is_empty(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records?limit=2&offset=99")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["items"] == []


def test_filters_sort_and_projection_combined(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/records",
        params={
            "clima": "arido",
            "sort": "score",
            "order": "desc",
            "fields": "id,nome,score",
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["sort"] == "score"
    assert body["order"] == "desc"
    assert body["fields"] == ["id", "nome", "score"]
    assert [item["id"] for item in body["items"]] == [1, 5]
    assert set(body["items"][0]) == {"id", "nome", "score"}


def test_repeated_filter_values_are_or(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/records",
        params=[("clima", "arido"), ("clima", "polar")],
    )

    assert response.status_code == 200
    assert response.json()["total"] == 5


def test_filter_numeric_and_boolean(client: TestClient) -> None:
    numeric = client.get("/api/v1/datasets/locais/records?id=2")
    boolean = client.get("/api/v1/datasets/locais/records?ativo=true")

    assert numeric.status_code == 200
    assert numeric.json()["total"] == 1
    assert numeric.json()["items"][0]["nome"] == "Askja"
    assert boolean.status_code == 200
    assert boolean.json()["total"] == 3


def test_filter_null(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records?score=null")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 6
    assert body["items"][0]["score"] is None


def test_filter_datetime_in_parquet(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/clusters/records?observado_em=2024-01-02"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 2


def test_filter_prefix_supports_reserved_column_names(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records?filter_limit=2")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_filter_column"


def test_get_record_by_id(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records/2")

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "locais"
    assert body["id"] == "2"
    assert body["id_column"] == "id"
    assert body["record"]["nome"] == "Askja"


def test_get_record_by_string_id(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/case1/ranking/records/r2")

    assert response.status_code == 200
    assert response.json()["record"]["score"] == 0.8


def test_get_record_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/records/999")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "record_not_found"
    assert detail["context"]["id"] == "999"


def test_empty_dataset_returns_empty_page(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/vazio/records")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("nao_existe=1", "invalid_filter_column"),
        ("sort=nao_existe", "invalid_sort_column"),
        ("fields=nao_existe", "invalid_field"),
        ("order=desc", "invalid_parameter"),
        ("limit=9999", "invalid_parameter"),
        ("limit=0", "invalid_parameter"),
        ("order=sideways", "invalid_parameter"),
        ("clima=arido&ativo=talvez", "invalid_filter_value"),
    ],
)
def test_invalid_query_parameters_return_400(
    client: TestClient, query: str, code: str
) -> None:
    response = client.get(f"/api/v1/datasets/locais/records?{query}")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert isinstance(detail["message"], str)
    assert isinstance(detail["context"], dict)


def test_fields_limit_is_enforced(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/records?fields=id,nome,pais,clima,score"
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_parameter"


def test_records_missing_dataset_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/nao_existe/records")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "dataset_not_found"
