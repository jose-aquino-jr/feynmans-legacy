"""Testes das rotas de análogos Terra ↔ Lua/Marte."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def analog_dir(tmp_path: Path) -> Path:
    root = tmp_path / "tratados"
    folder = root / "analogos"
    folder.mkdir(parents=True)
    pd.DataFrame({
        "base_id": ["MARTE_JEZERO", "LUA_POLO_SUL"], "corpo": ["marte", "lua"],
        "nome": ["Cratera Jezero", "Polo Sul lunar"], "descricao": ["paleolago", "polo"],
        "latitude": [18.38, -89.67], "longitude": [77.58, 129.78], "raio_km": [150.0, 100.0],
        "n_pares": [2, 1], "melhor_location_id": ["T1", "T2"], "melhor_nota": [83.0, 70.0],
    }).to_parquet(folder / "bases.parquet", index=False)
    pd.DataFrame({
        "location_id": ["T1", "T2"], "nome": ["Deserto da Núbia — Sudão", "Peary Land"],
        "regiao": ["Rio Nilo", None], "pais": ["Sudão", "Groenlândia"],
        "descricao": ["hiperárido", None], "destaque": [True, False],
        "latitude": [20.75, 82.75], "longitude": [33.25, -34.25], "raio_km": [150.0, 150.0],
        "n_pares": [1, 2], "melhor_nota": [83.0, 70.0],
        "temperatura_media_c": [28.2, -18.0], "precipitacao_mm_dia": [0.04, 0.3],
        "elevacao_media_m": [334.0, 600.0], "ndvi": [0.07, float("nan")],
    }).to_parquet(folder / "locais.parquet", index=False)
    pd.DataFrame({
        "par_id": ["MARTE_JEZERO__T1", "MARTE_JEZERO__T2", "LUA_POLO_SUL__T2"],
        "corpo": ["marte", "marte", "lua"],
        "base_id": ["MARTE_JEZERO", "MARTE_JEZERO", "LUA_POLO_SUL"],
        "location_id": ["T1", "T2", "T2"], "tipo": ["destaque", "especialista", "geral"],
        "destaque": [True, False, False], "nichos_destaque": ["", "termico", ""],
        "rank_base": [1, 2, 1], "nota_geral": [83.0, float("nan"), 70.0],
        "cobertura": [1.0, 0.6, 0.9], "pontos_fortes": ["geologia,agua_gelo", "termico", ""],
        "pontos_fracos": ["atmosfera", "geologia", "atmosfera"],
        "nota_logistica": [10.0, 90.0, 90.0],
        "custo_beneficio": [28.8, float("nan"), 79.4],
        "rank_custo_beneficio": [1.0, float("nan"), 1.0],
        "top_custo_beneficio": [False, False, True],
    }).to_parquet(folder / "pares.parquet", index=False)
    pd.DataFrame({
        "location_id": ["T2", "T2"], "ordem": [1, 2],
        "tipo_rota": ["principal", "alternativa"],
        "apoio_id": ["NASA-0100", "NASA-0101"], "nome": ["Pituffik", "Kangerlussuaq"],
        "categoria": ["Base de apoio em campanha"] * 2, "operador": ["USSF", "Groenlândia"],
        "pais": ["Groenlândia (Dinamarca)"] * 2, "vinculo": ["Interagência EUA", "Campanha"],
        "latitude": [76.5, 67.0], "longitude": [-68.7, -50.7],
        "prioridade": [0.68, 0.52], "distancia_km": [900.0, 1800.0],
        "peso_rota": [0.27, 0.09],
    }).to_parquet(folder / "rotas.parquet", index=False)
    pd.DataFrame({
        "apoio_id": ["NASA-0007", "NASA-0100", "RU-1"],
        "nome": ["Johnson Space Center", "Pituffik", "TsUP"],
        "categoria": ["Centro de campo NASA", "Base de apoio em campanha", "Posto"],
        "operador": ["NASA", "USSF", "Roscosmos"],
        "pais": ["Estados Unidos", "Groenlândia (Dinamarca)", "Rússia"],
        "latitude": [29.6, 76.5, 55.9], "longitude": [-95.1, -68.7, 37.8],
        "vinculo": ["Nativa NASA", "Interagência EUA", "Restrita"],
        "prioridade": [1.0, 0.68, 0.44], "eua": [True, False, False],
        "usado_na_logistica": [True, True, False],
    }).to_parquet(folder / "apoios.parquet", index=False)
    pd.DataFrame({
        "par_id": ["MARTE_JEZERO__T1", "MARTE_JEZERO__T1", "LUA_POLO_SUL__T2"],
        "corpo": ["marte", "marte", "lua"],
        "base_id": ["MARTE_JEZERO", "MARTE_JEZERO", "LUA_POLO_SUL"],
        "location_id": ["T1", "T1", "T2"], "nicho": ["geologia", "atmosfera", "termico"],
        "nota": [90.0, 0.0, float("nan")], "cobertura": [1.0, 1.0, 0.0],
    }).to_parquet(folder / "pares_nichos.parquet", index=False)
    pd.DataFrame({
        "par_id": ["MARTE_JEZERO__T1"] * 2, "anomes": [202609, 202608],
        "origem": ["prevista", "observada"], "nota": [82.5, 83.0], "cobertura": [1.0, 1.0],
    }).to_parquet(folder / "series.parquet", index=False)
    return root


@pytest.fixture()
def analog_client(analog_dir: Path, models_dir: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, environment="test", data_dir=analog_dir,
                        models_dir=models_dir, default_limit=100, max_limit=1_000)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def test_list_bases_filters_by_body(analog_client: TestClient) -> None:
    body = analog_client.get("/api/v1/analogos/bases", params={"corpo": "lua"}).json()
    assert body["total"] == 1
    assert body["items"][0]["base_id"] == "LUA_POLO_SUL"
    assert body["items"][0]["latitude"] == pytest.approx(-89.67)


def test_base_detail_embeds_site_and_niche_scores(analog_client: TestClient) -> None:
    response = analog_client.get("/api/v1/analogos/bases/MARTE_JEZERO")
    assert response.status_code == 200
    body = response.json()
    assert body["base"]["nome"] == "Cratera Jezero"
    assert body["total"] == 2
    first, second = body["pares"]
    assert first["local"]["nome"] == "Deserto da Núbia — Sudão"
    assert first["pontos_fortes"] == ["geologia", "agua_gelo"]
    assert first["nichos"] == {"geologia": 90.0, "atmosfera": 0.0}
    assert first["nichos_destaque"] == []
    assert second["nota_geral"] is None
    assert second["local"]["ndvi"] is None


def test_base_detail_filters(analog_client: TestClient) -> None:
    url = "/api/v1/analogos/bases/MARTE_JEZERO"
    assert analog_client.get(url, params={"destaque": "true"}).json()["total"] == 1
    assert analog_client.get(url, params={"tipo": "especialista"}).json()["total"] == 1
    assert analog_client.get(url, params={"forte_em": "termico"}).json()["total"] == 1
    assert analog_client.get(url, params={"nota_minima": 80}).json()["total"] == 1
    limited = analog_client.get(url, params={"limit": 1}).json()
    assert limited["total"] == 2
    assert len(limited["pares"]) == 1


def test_site_detail_lists_related_bases(analog_client: TestClient) -> None:
    body = analog_client.get("/api/v1/analogos/locais/T2").json()
    assert [pair["base_id"] for pair in body["pares"]] == ["LUA_POLO_SUL", "MARTE_JEZERO"]
    assert body["pares"][0]["base"]["corpo"] == "lua"
    assert body["pares"][0]["nichos"] == {"termico": None}
    assert [route["tipo_rota"] for route in body["rotas"]] == ["principal", "alternativa"]
    assert analog_client.get("/api/v1/analogos/locais/T1").json()["rotas"] == []


def test_cost_benefit_ranking_embeds_site_base_and_routes(analog_client: TestClient) -> None:
    url = "/api/v1/analogos/custo-beneficio"
    top = analog_client.get(url).json()
    assert top["total"] == 1
    item = top["items"][0]
    assert item["par_id"] == "LUA_POLO_SUL__T2"
    assert item["base"]["base_id"] == "LUA_POLO_SUL"
    assert item["local"]["location_id"] == "T2"
    assert [route["apoio_id"] for route in item["rotas"]] == ["NASA-0100", "NASA-0101"]
    everything = analog_client.get(url, params={"apenas_top": "false"}).json()
    assert [entry["custo_beneficio"] for entry in everything["items"]] == [79.4, 28.8]
    jezero = analog_client.get(url, params={"apenas_top": "false", "base_id": "MARTE_JEZERO"})
    assert jezero.json()["total"] == 1
    assert analog_client.get(url, params={"corpo": "marte"}).json()["total"] == 0
    missing = analog_client.get(url, params={"base_id": "NAO"})
    assert missing.status_code == 404


def test_base_detail_can_sort_by_cost_benefit(analog_client: TestClient) -> None:
    body = analog_client.get("/api/v1/analogos/bases/MARTE_JEZERO",
                             params={"ordenar": "custo_beneficio"}).json()
    assert [pair["location_id"] for pair in body["pares"]] == ["T1", "T2"]
    assert body["pares"][0]["top_custo_beneficio"] is False


def test_list_support_filters(analog_client: TestClient) -> None:
    url = "/api/v1/analogos/apoios"
    assert analog_client.get(url).json()["total"] == 3
    assert analog_client.get(url, params={"eua": "true"}).json()["total"] == 1
    used = analog_client.get(url, params={"usado": "true"}).json()
    assert {item["apoio_id"] for item in used["items"]} == {"NASA-0007", "NASA-0100"}
    by_category = analog_client.get(url, params={"categoria": "centro de campo nasa"})
    assert by_category.json()["total"] == 1


def test_list_sites_filters(analog_client: TestClient) -> None:
    url = "/api/v1/analogos/locais"
    assert analog_client.get(url).json()["total"] == 2
    featured = analog_client.get(url, params={"destaque": "true"}).json()
    assert [site["location_id"] for site in featured["items"]] == ["T1"]
    assert analog_client.get(url, params={"pais": "sudão"}).json()["total"] == 1


def test_pair_detail_has_sorted_series(analog_client: TestClient) -> None:
    body = analog_client.get("/api/v1/analogos/pares/MARTE_JEZERO__T1").json()
    assert body["base"]["base_id"] == "MARTE_JEZERO"
    assert body["local"]["location_id"] == "T1"
    assert [point["anomes"] for point in body["serie"]] == [202608, 202609]
    assert body["serie"][1]["origem"] == "prevista"
    assert body["rotas"] == []
    assert body["par"]["custo_beneficio"] == pytest.approx(28.8)


def test_list_niches(analog_client: TestClient) -> None:
    body = analog_client.get("/api/v1/analogos/nichos").json()
    by_id = {item["nicho"]: item for item in body["items"]}
    assert by_id["geologia"] == {"nicho": "geologia", "nome": "Geologia", "corpos": ["marte"]}
    assert by_id["termico"]["corpos"] == ["lua"]


@pytest.mark.parametrize(("url", "code"), [
    ("/api/v1/analogos/bases/NAO_EXISTE", "base_not_found"),
    ("/api/v1/analogos/locais/T999", "local_not_found"),
    ("/api/v1/analogos/pares/X__Y", "pair_not_found"),
])
def test_unknown_ids_return_404(analog_client: TestClient, url: str, code: str) -> None:
    response = analog_client.get(url)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == code


def test_invalid_body_returns_400(analog_client: TestClient) -> None:
    response = analog_client.get("/api/v1/analogos/bases", params={"corpo": "venus"})
    assert response.status_code == 400


def test_missing_tables_return_404(client: TestClient) -> None:
    response = client.get("/api/v1/analogos/bases")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "analogs_not_generated"
