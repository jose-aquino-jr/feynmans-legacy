"""Testes da ordenação de locais análogos com critérios ausentes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from feynmans_legacy.analog_study import recommend

# alvo, tolerância, peso
CRITERIA = {"a": (0.0, 10.0, 1.0), "b": (0.0, 10.0, 3.0)}


@pytest.fixture()
def coordinates() -> pd.DataFrame:
    return pd.DataFrame({
        "location_id": ["L1", "L2", "L3", "L4"],
        "latitude": [10.0, -80.0, 20.0, 30.0],
        "longitude": [0.0, 0.0, 0.0, 0.0],
    })


@pytest.fixture()
def values() -> pd.DataFrame:
    return pd.DataFrame({
        "location_id": ["L1", "L2", "L3", "L4"],
        "a": [5.0, 0.0, np.nan, np.nan],
        "b": [0.0, np.nan, 2.0, np.nan],
    })


def test_complete_location_keeps_weighted_score(
    values: pd.DataFrame, coordinates: pd.DataFrame
) -> None:
    ranking = recommend(values, coordinates, CRITERIA, min_coverage=0.2).set_index("location_id")
    assert ranking.loc["L1", "nota"] == pytest.approx((50 * 1 + 100 * 3) / 4)
    assert ranking.loc["L1", "cobertura"] == pytest.approx(1.0)
    assert ranking.loc["L1", "criterios_disponiveis"] == 2


def test_missing_criteria_are_renormalized(
    values: pd.DataFrame, coordinates: pd.DataFrame
) -> None:
    ranking = recommend(values, coordinates, CRITERIA, min_coverage=0.2).set_index("location_id")
    assert ranking.loc["L2", "nota"] == pytest.approx(100.0)
    assert ranking.loc["L2", "cobertura"] == pytest.approx(0.25)
    assert ranking.loc["L3", "nota"] == pytest.approx(80.0)
    assert ranking.loc["L3", "cobertura"] == pytest.approx(0.75)
    assert np.isnan(ranking.loc["L2", "nota_b"])


def test_min_coverage_filters_and_orders(
    values: pd.DataFrame, coordinates: pd.DataFrame
) -> None:
    ranking = recommend(values, coordinates, CRITERIA, min_coverage=0.5)
    assert ranking["location_id"].tolist() == ["L1", "L3"]
    strict = recommend(values, coordinates, CRITERIA, min_coverage=1.0)
    assert strict["location_id"].tolist() == ["L1"]


@pytest.mark.parametrize("min_coverage", [0.0, -0.1, 1.5])
def test_min_coverage_must_be_valid(
    values: pd.DataFrame, coordinates: pd.DataFrame, min_coverage: float
) -> None:
    with pytest.raises(ValueError, match="min_coverage"):
        recommend(values, coordinates, CRITERIA, min_coverage=min_coverage)


def test_reference_tolerance_prefers_per_base_column() -> None:
    from feynmans_legacy.analog_study import reference_tolerance

    mapping = {"terra": "x", "referencia": "x__alvo", "tolerancia": 10.0}
    assert reference_tolerance(pd.Series({"x__alvo": 1.0, "x__tolerancia": 3.0}),
                               mapping) == 3.0
    assert reference_tolerance(pd.Series({"x__alvo": 1.0, "x__tolerancia": np.nan}),
                               mapping) == 10.0
    assert reference_tolerance(pd.Series({"x__alvo": 1.0}), mapping) == 10.0
