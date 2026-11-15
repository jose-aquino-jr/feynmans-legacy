"""Testes das agregações genéricas."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_count_without_group(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/aggregations?agg=count")

    assert response.status_code == 200
    body = response.json()
    assert body["aggregations"] == ["count"]
    assert body["columns"] == []
    assert body["group_by"] == []
    assert body["total_groups"] == 1
    assert body["items"] == [{"group": {}, "values": {"count": 6}}]


def test_count_group_by_and_pagination(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations",
        params={"agg": "count", "group_by": "clima", "limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_groups"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2
    assert [item["group"]["clima"] for item in body["items"]] == ["frio", "polar"]


def test_multiple_aggregations(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations",
        params=[("agg", "min"), ("agg", "max"), ("column", "score")],
    )

    assert response.status_code == 200
    values = response.json()["items"][0]["values"]
    assert values["min_score"] == 0.6
    assert values["max_score"] == 0.91


def test_mean_group_by_with_filter(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations",
        params={
            "agg": "mean",
            "column": "score",
            "group_by": "clima",
            "clima": "arido",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_groups"] == 1
    assert body["items"][0]["group"] == {"clima": "arido"}
    assert body["items"][0]["values"]["mean_score"] == 0.865


def test_count_non_null_column(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations",
        params={"agg": "count", "column": "score"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["values"] == {"count_score": 5}


def test_sum_and_missing_group_value_in_parquet(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/clusters/aggregations",
        params={"agg": "sum", "column": "peso", "group_by": "cluster"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["group"] == {"cluster": 0}
    assert items[0]["values"]["sum_peso"] is None
    assert items[1]["values"]["sum_peso"] == 4.0


def test_aggregation_invalid_name(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/aggregations?agg=median")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_aggregation"
    assert detail["context"]["invalid"] == ["median"]


def test_mean_requires_column(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/aggregations?agg=mean")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_aggregation_column"


def test_mean_requires_numeric_column(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations?agg=mean&column=nome"
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_aggregation_column"


def test_aggregation_invalid_group_by(client: TestClient) -> None:
    response = client.get(
        "/api/v1/datasets/locais/aggregations?agg=count&group_by=nao_existe"
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_group_by_column"
    assert detail["context"]["columns"] == ["nao_existe"]


def test_aggregation_limit_is_enforced(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/locais/aggregations?agg=count&limit=9999")

    assert response.status_code == 400
    assert response.json()["detail"]["context"]["max"] == 1_000
