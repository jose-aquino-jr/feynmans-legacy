"""Testes da API de recomendações temporais com uma publicação em miniatura."""

from __future__ import annotations

import json
import pickle
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from app.config import Settings
from app.main import create_app
from app.services.recommendations import Job
from fastapi.testclient import TestClient

from feynmans_legacy.analog_study import recommend

TEMP = "temperatura__ar_2m_c"
RELEVO = "relevo__amplitude_relevo_m"
URL = "/api/v1/analogos/recomendacoes"
IDS = ["T0001", "T0002", "T0003", "T0004"]


def write_publication(root: Path, *, model: object | None = None) -> Settings:
    (root / "config").mkdir(parents=True)
    (root / "data/lua").mkdir(parents=True)
    (root / "data/marte").mkdir(parents=True)
    run = root / "run"
    (run / "modelos").mkdir(parents=True)
    termico = [{"terra": TEMP, "referencia": f"{TEMP}__alvo", "tolerancia": 10.0}]
    terreno = [{"terra": RELEVO, "referencia": f"{RELEVO}__alvo", "tolerancia": 100.0}]
    (root / "config/nichos.json").write_text(json.dumps({
        "lua": {"termico": termico, "terreno": terreno}, "marte": {"termico": termico},
    }), encoding="utf-8")
    (root / "config/bases_espaciais.json").write_text(json.dumps({
        "L1": {"corpo": "lua", "nome": "Lua 1", "latitude": -89.6, "longitude": 129.7,
               "raio_km": 100},
        "L2": {"corpo": "lua", "nome": "Lua 2", "latitude": 14.1, "longitude": -56.8,
               "raio_km": 100},
        "M1": {"corpo": "marte", "nome": "Marte 1", "latitude": 18.4, "longitude": 77.6,
               "raio_km": 150},
    }), encoding="utf-8")
    pd.DataFrame({"base_id": ["L1", "L2"], "descricao": ["a", "b"], "status": ["x", "x"],
                  f"{TEMP}__alvo": [0.0, 20.0], f"{RELEVO}__alvo": [0.0, 100.0]}
                 ).to_parquet(root / "data/lua/lua.parquet", index=False)
    pd.DataFrame({"base_id": ["M1"], "descricao": ["c"], "status": ["x"],
                  f"{TEMP}__alvo": [5.0]}).to_parquet(root / "data/marte/marte.parquet",
                                                    index=False)
    pd.DataFrame({"location_id": IDS, "latitude": [10.0, -20.0, 45.5, 0.0],
                  "longitude": [-70.25, 120.0, -0.5, 10.0]}
                 ).to_parquet(run / "coordenadas.parquet", index=False)
    pd.DataFrame({"location_id": IDS, RELEVO: [0.0, 50.0, 100.0, 0.0]}
                 ).to_parquet(run / "estaticas.parquet", index=False)
    pd.DataFrame({"location_id": IDS, "anomes": 202512, "cluster": [0, 1, 1, 2]}
                 ).to_parquet(run / "clusters.parquet", index=False)
    rows = []
    for month in pd.period_range("2024-01", "2025-12", freq="M"):
        anomes = int(month.strftime("%Y%m"))
        for location, value in zip(IDS, [0.0, 5.0, 10.0, 3.0], strict=True):
            if anomes == 202406 or (location == "T0004" and anomes == 202512):
                value = np.nan
            rows.append({"location_id": location, "anomes": anomes, TEMP: value})
    pd.DataFrame(rows).to_parquet(root / "terra.parquet", index=False)
    models = model if model is not None else {(TEMP, h): None for h in (1, 2, 3)}
    (run / "modelos/previsao_mensal.pkl").write_bytes(
        pickle.dumps({"origem": "2025-12", "modelos": models}))
    return Settings(
        _env_file=None, environment="test", data_dir=root / "tratados",
        recomendacoes_terra_path=root / "terra.parquet", recomendacoes_run_dir=run,
        recomendacoes_modelo_path=run / "modelos/previsao_mensal.pkl",
        recomendacoes_cache_dir=root / "cache", recomendacoes_config_dir=root / "config",
        recomendacoes_perfis_dir=root / "data", recomendacoes_retry_segundos=1,
        recomendacoes_anomes_max=210012)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return write_publication(tmp_path)


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


def get(client: TestClient, **params: Any) -> Any:
    return client.get(URL, params=params)


def group(body: dict[str, Any], base: str) -> dict[str, Any]:
    return next(g for g in body["resultados"] if g["base_id"] == base)


def ids(found: dict[str, Any]) -> list[str]:
    return [c["location_id"] for c in found["candidatos"]]


def finish(client: TestClient) -> None:
    client.app.state.recommendation_service.wait(60)  # type: ignore[attr-defined]


def test_options_list_bases_niches_and_months(client: TestClient) -> None:
    body = client.get(f"{URL}/opcoes").json()
    bases = {b["base_id"]: b for b in body["bases"]}
    assert set(bases) == {"L1", "L2", "M1"}
    assert bases["L1"]["nichos"] == ["Todos", "termico", "terreno"]
    assert bases["M1"]["nichos"] == ["Todos", "termico"]
    assert body["meses_observados"][0] == 202401 and body["meses_observados"][-1] == 202512
    assert body["publicacao"]["corte"] == 202512
    assert body["publicacao"]["horizontes_diretos"] == {TEMP: [1, 2, 3]}


def test_observed_ranking_scores_ties_and_pages(client: TestClient) -> None:
    body = get(client, anomes=202512).json()
    assert body["origem"] == "observada" and body["horizonte_meses"] == 0
    l1, m1 = group(body, "L1"), group(body, "M1")
    assert ids(l1) == ["T0001", "T0002", "T0003"]  # T0004 has coverage 0.5 < 0.7
    assert [c["nota"] for c in l1["candidatos"]] == [100.0, 50.0, 0.0]
    assert l1["total_elegiveis"] == 3 and l1["status"] == "ok"
    first = l1["candidatos"][0]
    assert first["latitude"] == 10.0 and first["longitude"] == -70.25
    assert first["cluster"] == 0 and first["valores"] == {TEMP: 0.0, RELEVO: 0.0}
    assert ids(m1) == ["T0002", "T0001", "T0003"]  # tie at 50 -> location_id
    page = get(client, anomes=202512, base_id="L1", k=1, offset=1).json()
    assert [(c["posicao"], c["location_id"]) for c in group(page, "L1")["candidatos"]] == [
        (2, "T0002")]
    assert group(page, "L1")["total_elegiveis"] == 3


def test_coverage_threshold(client: TestClient) -> None:
    loose = group(get(client, anomes=202512, base_id="L1", cobertura_minima=0.5).json(), "L1")
    assert ids(loose)[:2] == ["T0001", "T0004"]
    t4 = loose["candidatos"][1]
    assert t4["cobertura"] == 0.5 and t4["criterios_sem_dado"] == [TEMP]
    strict = group(get(client, anomes=202512, base_id="L1", cobertura_minima=1).json(), "L1")
    assert ids(strict) == ["T0001", "T0002", "T0003"]


def test_niche_restricts_criteria_and_flags_incompatible_base(client: TestClient) -> None:
    body = get(client, anomes=202512, nicho="terreno").json()
    assert group(body, "M1")["status"] == "nicho_incompativel"
    l1 = group(body, "L1")
    assert [c["variavel"] for c in l1["criterios"]] == [RELEVO]
    assert ids(l1) == ["T0001", "T0004", "T0002", "T0003"]
    assert group(get(client, anomes=202512).json(), "L1")["criterios"][0]["variavel"] == TEMP


def test_same_location_competes_in_every_base(client: TestClient) -> None:
    body = get(client, anomes=202512).json()
    assert all("T0001" in ids(g) for g in body["resultados"])


def test_criterion_missing_everywhere(client: TestClient) -> None:
    body = get(client, anomes=202406).json()
    assert group(body, "M1")["status"] == "sem_dados"
    assert group(body, "M1")["criterios_ausentes"] == [TEMP]
    assert group(body, "L1")["status"] == "sem_dados"
    relaxed = get(client, anomes=202406, cobertura_minima=0.5).json()
    assert group(relaxed, "L1")["status"] == "parcial"


def test_no_eligible_candidate_is_different_from_missing_data(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = client.app.state.recommendation_service  # type: ignore[attr-defined]
    empty = pd.DataFrame(columns=["location_id", "latitude", "longitude", "nota", "cobertura"])
    monkeypatch.setattr(service, "_ranking", lambda *args, **kwargs: empty)
    body = get(client, anomes=202512, base_id="L1").json()
    found = group(body, "L1")
    assert found["status"] == "sem_candidatos" and found["criterios_ausentes"] == []
    assert found["total_elegiveis"] == 0 and found["candidatos"] == []


def test_matches_reference_recommend(client: TestClient, settings: Settings) -> None:
    body = get(client, anomes=202512, base_id="M1", k=10).json()
    terra = pd.read_parquet(settings.recomendacoes_terra_path)
    month = terra[terra["anomes"] == 202512].drop(columns="anomes")
    coords = pd.read_parquet(settings.recomendacoes_run_dir / "coordenadas.parquet")
    expected = recommend(month, coords, {TEMP: (5.0, 10.0, 1.0)})
    assert ids(group(body, "M1")) == expected["location_id"].tolist()
    assert [c["nota"] for c in group(body, "M1")["candidatos"]] == pytest.approx(
        expected["nota"].tolist())


@pytest.mark.parametrize(("params", "status", "code"), [
    ({"anomes": 202613}, 400, "anomes_invalido"),
    ({"anomes": 202301}, 404, "anterior_ao_historico"),
    ({"anomes": 210101}, 400, "anomes_fora_do_calendario"),
    ({"anomes": 202512, "nicho": "nao_existe"}, 400, "nicho_invalido"),
    ({"anomes": 202512, "base_id": "M1", "corpo": "lua"}, 400, "base_corpo_incoerente"),
    ({"anomes": 202512, "base_id": "XX"}, 404, "base_not_found"),
    ({"anomes": 202512, "k": 0}, 400, "invalid_parameter"),
])
def test_invalid_requests(client: TestClient, params: dict[str, Any], status: int,
                          code: str) -> None:
    response = get(client, **params)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_recursive_future_returns_202_then_200(client: TestClient) -> None:
    first = get(client, anomes=202601, estrategia="recursiva", base_id="M1")
    assert first.status_code == 202
    assert first.headers["Retry-After"] == "1"
    assert first.json()["status"] == "calculando" and first.json()["meses_necessarios"] == 1
    again = get(client, anomes=202601, estrategia="recursiva", base_id="M1")
    if again.status_code == 202:
        assert again.json()["tarefa_id"] == first.json()["tarefa_id"]  # deduplicated
    finish(client)
    body = get(client, anomes=202601, estrategia="recursiva", base_id="M1").json()
    assert body["origem"] == "prevista" and body["horizonte_meses"] == 1
    assert body["metodos"] == {TEMP: "persistencia_h1"} and body["rotulo"] is None
    assert ids(group(body, "M1")) == ["T0002", "T0001", "T0003"]


def test_recursive_beyond_direct_horizons(client: TestClient, settings: Settings) -> None:
    assert get(client, anomes=202606, estrategia="recursiva").status_code == 202
    finish(client)
    body = get(client, anomes=202606, estrategia="recursiva").json()
    assert body["origem"] == "extrapolada" and body["horizonte_meses"] == 6
    assert body["rotulo"] == "Projeção exploratória" and body["estrategia"] == "recursiva"
    assert body["metodos"] == {TEMP: "persistencia_h3"}
    trajectory = body["publicacao"]["trajetoria"]
    stored = sorted(p.name for p in (settings.recomendacoes_cache_dir / trajectory).glob(
        "*.parquet"))
    assert stored[0] == "202601.parquet" and stored[-1] == "202606.parquet"
    # Restart: a new process reuses the checkpoints and answers immediately.
    with TestClient(create_app(settings)) as fresh:
        assert get(fresh, anomes=202606, estrategia="recursiva").status_code == 200
        # A later month continues from the stored trajectory.
        assert get(fresh, anomes=202607, estrategia="recursiva").json()["meses_calculados"] == 6


def test_seasonal_scenario_does_not_touch_trajectory(client: TestClient,
                                                     settings: Settings) -> None:
    body = get(client, anomes=204007, estrategia="auto").json()
    assert body["origem"] == "cenario_sazonal" and body["mes_base_cenario"] == 202507
    assert body["horizonte_meses"] == 175
    assert body["metodos"] == {TEMP: "observado_202507"}
    assert not settings.recomendacoes_cache_dir.exists() or not any(
        settings.recomendacoes_cache_dir.rglob("*.parquet"))
    sazonal = get(client, anomes=202601, estrategia="sazonal").json()
    assert sazonal["origem"] == "cenario_sazonal" and sazonal["mes_base_cenario"] == 202501


def test_auto_within_direct_horizon_uses_projection(client: TestClient) -> None:
    assert get(client, anomes=202602, estrategia="auto").status_code == 202
    finish(client)
    body = get(client, anomes=202602, estrategia="auto").json()
    assert body["origem"] == "prevista" and body["metodos"] == {TEMP: "persistencia_h2"}


def test_failed_projection_reports_actionable_error(client: TestClient,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.recommendations as module

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(module, "project_until", boom)
    assert get(client, anomes=202603, estrategia="recursiva").status_code == 202
    finish(client)
    response = get(client, anomes=202603, estrategia="recursiva")
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "projecao_falhou"
    assert "disco cheio" in response.json()["detail"]["context"]["erro"]


def test_queue_saturation(client: TestClient) -> None:
    service = client.app.state.recommendation_service  # type: ignore[attr-defined]
    service.settings.recomendacoes_fila_max = 1
    service._jobs["outra"] = Job(id="x", target=pd.Period("2026-01", freq="M"),
                                 status="rodando")
    response = get(client, anomes=202605, estrategia="recursiva")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "fila_cheia"


def test_inconsistent_publication_is_unavailable(tmp_path: Path) -> None:
    settings = write_publication(tmp_path)
    settings.recomendacoes_modelo_path.write_bytes(
        pickle.dumps({"origem": "2025-11", "modelos": {(TEMP, 1): None}}))
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = get(client, anomes=202512)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "publicacao_indisponivel"
