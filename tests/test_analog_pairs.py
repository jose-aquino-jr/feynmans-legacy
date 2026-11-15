"""Testes da seleção de pares Terra ↔ Lua/Marte."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from feynmans_legacy.analog_pairs import (
    SelectionConfig,
    Zone,
    haversine_km,
    land_locations,
    outside_zones,
    pick_spread,
    select_locations,
    strengths,
)


def test_haversine_known_distance() -> None:
    # One degree of latitude is about 111 km.
    assert haversine_km(np.array([0.0]), np.array([0.0]), 1.0, 0.0)[0] == pytest.approx(
        111.19, abs=0.1)


def test_outside_zones_excludes_points_inside_radius() -> None:
    frame = pd.DataFrame({"latitude": [-24.0, 0.0], "longitude": [-68.5, 0.0]})
    keep = outside_zones(frame, [Zone("Atacama", -24.0, -68.5, 500.0)])
    assert keep.tolist() == [False, True]


def test_pick_spread_skips_nearby_points() -> None:
    ranked = pd.DataFrame(
        {"latitude": [10.0, 10.5, 30.0, 50.0], "longitude": [0.0, 0.0, 0.0, 0.0]},
        index=["a", "b", "c", "d"],
    )
    assert pick_spread(ranked, k=2, min_km=500).index.tolist() == ["a", "c"]
    assert pick_spread(ranked, k=10, min_km=500).index.tolist() == ["a", "c", "d"]


def test_select_locations_mixes_general_and_specialists() -> None:
    scores = pd.DataFrame({
        "latitude": [0.0, 20.0, 40.0, -24.0],
        "longitude": [0.0, 0.0, 0.0, -68.5],
        "nota_geral": [90.0, 60.0, np.nan, 99.0],
        "nota_termico": [50.0, 95.0, 85.0, 99.0],
    }, index=["geral", "quente", "sem_geral", "atacama"])
    picks = select_locations(
        scores, ["termico"], [Zone("Atacama", -24.0, -68.5, 300.0)],
        SelectionConfig(n_geral=1, n_por_nicho=2, min_nota_nicho=80, separacao_km=500),
    )
    assert picks == {
        "geral": ("geral", []),
        "quente": ("especialista", ["termico"]),
        "sem_geral": ("especialista", ["termico"]),
    }


def test_strengths_lists_best_and_worst_niches() -> None:
    row = pd.Series({"nota_a": 90.0, "nota_b": 76.0, "nota_c": 10.0, "nota_d": np.nan})
    assert strengths(row, ["a", "b", "c", "d"]) == ("a,b", "c")


def test_land_locations_drops_water_cells() -> None:
    values = pd.DataFrame({"location_id": ["T1", "T2", "T3"],
                           "biologia__cobertura_agua_fracao": [0.0, 0.9, np.nan]})
    assert land_locations(values) == {"T1", "T3"}
