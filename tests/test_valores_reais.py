"""Testes da troca de alvos-proxy por valores reais."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aplicar_valores_reais.py"
spec = importlib.util.spec_from_file_location("aplicar_valores_reais", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_relative_tolerance_reaches_far_percentile() -> None:
    earth = pd.Series(range(50, 104), dtype=float)  # pressão terrestre (kPa)
    tolerance = module.relative_tolerance(earth, 0.7)
    assert tolerance == pytest.approx(earth.quantile(0.99) - 0.7)
    with pytest.raises(ValueError):
        module.relative_tolerance(pd.Series([1.0, 1.0]), 1.0)


def test_apply_real_values_updates_spec_and_catalog() -> None:
    real = pd.DataFrame({
        "corpo": ["marte"], "base_id": ["B1"], "variavel": ["p"], "valor_real": [0.7],
        "confianca": ["media"], "fonte": ["MEDA"],
    })
    earth = pd.DataFrame({"p": [50.0, 80.0, 103.0]})
    spec = pd.DataFrame({"base_id": ["B1", "B2"], "status": ["x", "x"],
                         "p__alvo": [49.0, 49.0]})
    catalog = pd.DataFrame({
        "corpo": ["marte", "marte"], "base_id": ["B1", "B2"], "terra": ["p", "p"],
        "alvo": [49.0, 49.0], "regra_alvo": ["percentil 0 da Terra"] * 2,
        "tolerancia": [33.5, 33.5], "regra_tolerancia": ["p95 − p5"] * 2,
    })
    specs, updated = module.apply_real_values(real, earth, {"marte": spec}, catalog)
    out = specs["marte"].set_index("base_id")
    assert out.loc["B1", "p__alvo"] == 0.7
    assert out.loc["B2", "p__alvo"] == 49.0
    assert out.loc["B1", "p__tolerancia"] == pytest.approx(
        earth["p"].quantile(0.99) - 0.7)
    assert pd.isna(out.loc["B2", "p__tolerancia"])
    row = updated.set_index("base_id").loc["B1"]
    assert row["alvo"] == 0.7 and row["alvo_proxy"] == 49.0
    assert row["regra_alvo"] == "valor real (media): MEDA"
    assert spec.loc[0, "p__alvo"] == 49.0  # input untouched
    again, _ = module.apply_real_values(real, earth, {"marte": specs["marte"]}, updated)
    assert again["marte"].equals(specs["marte"])
