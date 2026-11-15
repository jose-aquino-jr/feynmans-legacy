"""Testes da logística dos análogos (EUA, bases de apoio e rotas)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from feynmans_legacy.logistics import (
    LogisticsConfig,
    cost_benefit,
    distance_matrix,
    logistics_scores,
    support_routes,
    usable_support,
)

CONFIG = LogisticsConfig(escala_eua_km=1000, escala_apoio_km=1000, raio_rotas_km=500,
                         saturacao_rotas=2.0, peso_eua=0.5, peso_apoio=0.25,
                         peso_rotas=0.25, n_rotas=2)


@pytest.fixture()
def support() -> pd.DataFrame:
    return pd.DataFrame({
        "apoio_id": ["US", "PARCEIRO", "RESTRITA", "OCEANO"],
        "nome": ["Base EUA", "Base parceira", "Restrita", "Zona no mar"],
        "categoria": ["c"] * 4, "operador": ["o"] * 4,
        "pais": ["Estados Unidos", "Chile", "Rússia", "Águas internacionais"],
        "continente": ["América do Norte", "América do Sul", "Europa", "Oceano"],
        "vinculo": ["Nativa NASA", "Acordo internacional", "Restrita", "Comercial"],
        "latitude": [0.0, 0.0, 0.0, 0.0], "longitude": [0.0, 2.0, 1.0, 1.0],
        "prioridade": [1.0, 0.5, 1.0, 1.0],
        "eua": [True, False, False, False],
    })


def test_distance_matrix_shape_and_values() -> None:
    distance = distance_matrix(np.array([0.0, 0.0]), np.array([0.0, 1.0]),
                               np.array([0.0]), np.array([0.0]))
    assert distance.shape == (2, 1)
    assert distance[0, 0] == pytest.approx(0.0)
    assert distance[1, 0] == pytest.approx(111.19, abs=0.1)


def test_usable_support_drops_restricted_and_ocean(support: pd.DataFrame) -> None:
    assert usable_support(support, CONFIG)["apoio_id"].tolist() == ["US", "PARCEIRO"]


def test_logistics_scores_combine_us_support_and_routes(support: pd.DataFrame) -> None:
    coordinates = pd.DataFrame({"location_id": ["perto", "longe"],
                                "latitude": [0.0, 60.0], "longitude": [0.0, 0.0]})
    scores = logistics_scores(coordinates, usable_support(support, CONFIG), CONFIG)
    near = scores.loc["perto"]
    assert near["distancia_eua_km"] == pytest.approx(0.0)
    assert near["apoio_principal_id"] == "US"
    assert near["n_apoios_raio"] == 2
    assert near["nota_eua"] == pytest.approx(100.0)
    assert near["nota_rotas"] == pytest.approx(75.0)  # (1.0 + 0.5) / 2
    assert near["nota_logistica"] == pytest.approx(0.5 * 100 + 0.25 * 100 + 0.25 * 75)
    far = scores.loc["longe"]
    assert far["n_apoios_raio"] == 0
    assert far["nota_logistica"] < near["nota_logistica"]


def test_support_routes_rank_main_and_alternatives(support: pd.DataFrame) -> None:
    coordinates = pd.DataFrame({"location_id": ["L"], "latitude": [0.0],
                                "longitude": [2.0]})
    routes = support_routes(coordinates, usable_support(support, CONFIG), CONFIG)
    assert routes["tipo_rota"].tolist() == ["principal", "alternativa"]
    # The partner base sits on the site (weight 0.5); the US base is 222 km away but
    # has double priority (weight 1.0 × exp(-0.222) ≈ 0.80), so it is the main route.
    assert routes["apoio_id"].tolist() == ["US", "PARCEIRO"]
    assert routes["distancia_km"].iloc[0] == pytest.approx(222.4, abs=0.2)
    assert routes["distancia_km"].iloc[1] == pytest.approx(0.0)


def test_cost_benefit_is_geometric_mean() -> None:
    result = cost_benefit(pd.Series([81.0, np.nan, 50.0]), pd.Series([49.0, 90.0, 0.0]))
    assert result.iloc[0] == pytest.approx(63.0)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 0.0


def test_config_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "custo_beneficio.json"
    path.write_text(json.dumps({"_descricao": "x", "peso_eua": 0.6,
                                "vinculos_excluidos": ["Restrita", "Comercial"]}),
                    encoding="utf-8")
    config = LogisticsConfig.from_json(path)
    assert config.peso_eua == 0.6
    assert config.vinculos_excluidos == ("Restrita", "Comercial")
    assert config.n_rotas == 3
