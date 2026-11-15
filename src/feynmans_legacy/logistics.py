"""Logística de campo dos análogos: EUA, bases de apoio e rotas alternativas.

A nota de logística (0–100) combina três partes, com pesos em
``config/custo_beneficio.json``:

* ``nota_eua``: proximidade da instalação dos EUA mais próxima;
* ``nota_apoio``: a melhor base de apoio, ponderando prioridade e distância;
* ``nota_rotas``: redundância, isto é, quantas bases boas existem no raio.

O custo-benefício de um par é a média geométrica entre a nota do análogo e a
nota de logística: um local só fica bem colocado se for bom nas duas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0
SUPPORT_RENAMES = {"id": "apoio_id", "lat": "latitude", "lon": "longitude",
                   "prioridade_combinada": "prioridade"}
SUPPORT_COLUMNS = ["apoio_id", "nome", "categoria", "subcategoria", "operador",
                   "tipo_operador", "pais", "continente", "local", "latitude", "longitude",
                   "coord_precisao", "capacidades", "programas", "vinculo", "status",
                   "relevancia_score", "compatibilidade_score", "prioridade"]


@dataclass(frozen=True)
class LogisticsConfig:
    escala_eua_km: float = 3000.0
    escala_apoio_km: float = 1000.0
    raio_rotas_km: float = 2500.0
    saturacao_rotas: float = 3.0
    peso_eua: float = 0.4
    peso_apoio: float = 0.35
    peso_rotas: float = 0.25
    n_rotas: int = 3
    n_custo_beneficio: int = 8
    fracao_nota_minima: float = 0.8
    vinculos_excluidos: tuple[str, ...] = ("Restrita",)
    continentes_excluidos: tuple[str, ...] = ("Oceano",)

    @classmethod
    def from_json(cls, path: Path) -> LogisticsConfig:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        known = {item.name for item in fields(cls)}
        values: dict[str, Any] = {key: tuple(value) if isinstance(value, list) else value
                                  for key, value in raw.items() if key in known}
        return cls(**values)


def load_support(path: Path) -> pd.DataFrame:
    """Read the support-base catalog (GeoParquet) without the WKB geometry."""
    frame = pd.read_parquet(path).rename(columns=SUPPORT_RENAMES)
    frame = frame[[column for column in SUPPORT_COLUMNS if column in frame.columns]]
    for column in frame.select_dtypes(include="category").columns:
        frame[column] = frame[column].astype(str)
    frame["eua"] = frame["pais"].astype(str).str.startswith("Estados Unidos")
    return frame.reset_index(drop=True)


def usable_support(support: pd.DataFrame, config: LogisticsConfig) -> pd.DataFrame:
    """Bases that can back a field campaign (no restricted links, no open ocean)."""
    keep = ~support["vinculo"].isin(config.vinculos_excluidos)
    if "continente" in support.columns:
        keep &= ~support["continente"].isin(config.continentes_excluidos)
    return support[keep].reset_index(drop=True)


def distance_matrix(lat_a: np.ndarray, lon_a: np.ndarray,
                    lat_b: np.ndarray, lon_b: np.ndarray) -> np.ndarray:
    """Great-circle distances (km) between every point of A and every point of B."""
    phi_a, lam_a = np.radians(lat_a)[:, None], np.radians(lon_a)[:, None]
    phi_b, lam_b = np.radians(lat_b)[None, :], np.radians(lon_b)[None, :]
    half = (np.sin((phi_b - phi_a) / 2) ** 2
            + np.cos(phi_a) * np.cos(phi_b) * np.sin((lam_b - lam_a) / 2) ** 2)
    return np.asarray(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(half, 0, 1))))


def logistics_scores(coordinates: pd.DataFrame, support: pd.DataFrame,
                     config: LogisticsConfig, chunk: int = 4096) -> pd.DataFrame:
    """Logistics score of every location (indexed by ``location_id``)."""
    lat_b = support["latitude"].to_numpy(dtype=float)
    lon_b = support["longitude"].to_numpy(dtype=float)
    priority = support["prioridade"].to_numpy(dtype=float)
    us = support["eua"].to_numpy(dtype=bool)
    ids = support["apoio_id"].to_numpy()
    parts = []
    for start in range(0, len(coordinates), chunk):
        block = coordinates.iloc[start:start + chunk]
        distance = distance_matrix(block["latitude"].to_numpy(dtype=float),
                                   block["longitude"].to_numpy(dtype=float), lat_b, lon_b)
        weighted = priority * np.exp(-distance / config.escala_apoio_km)
        best = weighted.argmax(axis=1)
        rows = np.arange(len(block))
        in_reach = distance <= config.raio_rotas_km
        us_distance = distance[:, us].min(axis=1) if us.any() else np.full(len(block), np.inf)
        parts.append(pd.DataFrame({
            "location_id": block["location_id"].to_numpy(),
            "distancia_eua_km": us_distance,
            "apoio_principal_id": ids[best],
            "distancia_apoio_km": distance[rows, best],
            "n_apoios_raio": in_reach.sum(axis=1),
            "nota_eua": 100 * np.exp(-us_distance / config.escala_eua_km),
            "nota_apoio": 100 * weighted[rows, best],
            "nota_rotas": 100 * np.minimum(
                1.0, (priority * in_reach).sum(axis=1) / config.saturacao_rotas),
        }))
    scores = pd.concat(parts, ignore_index=True).set_index("location_id")
    scores["nota_logistica"] = (config.peso_eua * scores["nota_eua"]
                                + config.peso_apoio * scores["nota_apoio"]
                                + config.peso_rotas * scores["nota_rotas"])
    return scores


def support_routes(coordinates: pd.DataFrame, support: pd.DataFrame,
                   config: LogisticsConfig) -> pd.DataFrame:
    """Main and alternative support bases of each location, best first."""
    distance = distance_matrix(coordinates["latitude"].to_numpy(dtype=float),
                               coordinates["longitude"].to_numpy(dtype=float),
                               support["latitude"].to_numpy(dtype=float),
                               support["longitude"].to_numpy(dtype=float))
    weighted = support["prioridade"].to_numpy(dtype=float) * np.exp(
        -distance / config.escala_apoio_km)
    order = np.argsort(-weighted, axis=1, kind="stable")[:, :config.n_rotas]
    rows = []
    columns = ["apoio_id", "nome", "categoria", "operador", "pais", "vinculo",
               "latitude", "longitude", "prioridade"]
    for position, location in enumerate(coordinates["location_id"].to_numpy()):
        for rank, index in enumerate(order[position], start=1):
            base = support.iloc[int(index)]
            rows.append({
                "location_id": str(location), "ordem": rank,
                "tipo_rota": "principal" if rank == 1 else "alternativa",
                **{column: base[column] for column in columns},
                "distancia_km": float(distance[position, index]),
                "peso_rota": float(weighted[position, index]),
            })
    return pd.DataFrame(rows)


def cost_benefit(score: pd.Series, logistics: pd.Series) -> pd.Series:
    """Geometric mean of analog score and logistics score (0–100)."""
    return np.sqrt(score.clip(lower=0) * logistics.clip(lower=0))
