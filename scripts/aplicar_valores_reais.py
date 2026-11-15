"""Troca alvos-proxy das bases da Lua e de Marte por valores reais com fonte.

Lê ``config/valores_reais.csv`` e, para cada base e variável listada:

* grava o valor real em ``data/<corpo>/<corpo>.parquet`` (coluna ``<var>__alvo``);
* grava uma tolerância própria da base em ``<var>__tolerancia``: a maior
  distância entre o alvo e os percentis 1 e 99 da Terra. Assim o lugar da Terra
  mais próximo do valor real pontua e os demais caem proporcionalmente, mesmo
  quando o valor real está fora do alcance terrestre (ex.: pressão de Marte);
* atualiza ``config/criterios_referencia_proposta.csv`` (alvo, regra, tolerância)
  guardando o proxy anterior em ``alvo_proxy``.

O script é idempotente. Depois rode ``python scripts/gerar_analogos.py``.

Uso:  python scripts/aplicar_valores_reais.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feynmans_legacy.analog_pairs import load_inputs  # noqa: E402
from feynmans_legacy.analog_study import TOLERANCE_SUFFIX  # noqa: E402

REAL_VALUES = ROOT / "config/valores_reais.csv"
CATALOG = ROOT / "config/criterios_referencia_proposta.csv"
TOLERANCE_RULE = "real: maior distância do alvo aos percentis 1 e 99 da Terra"
STATUS = ("Alvos reais com fonte em config/valores_reais.csv; variáveis sem medida "
          "equivalente seguem como equivalente terrestre ou classificação da equipe")


def relative_tolerance(earth: pd.Series, target: float) -> float:
    """Largest distance between the target and Earth's 1st/99th percentiles."""
    low, high = earth.dropna().quantile([0.01, 0.99])
    tolerance = max(abs(float(low) - target), abs(float(high) - target))
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError(f"Tolerância inválida para alvo {target}")
    return tolerance


def apply_real_values(real: pd.DataFrame, earth: pd.DataFrame,
                      references: dict[str, pd.DataFrame],
                      catalog: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Return updated reference specs and catalog (inputs are not modified)."""
    specs = {body: frame.copy() for body, frame in references.items()}
    catalog = catalog.copy()
    if "alvo_proxy" not in catalog.columns:
        catalog["alvo_proxy"] = catalog["alvo"]
    for row in real.itertuples(index=False):
        body, base_id, variable = str(row.corpo), str(row.base_id), str(row.variavel)
        target = float(row.valor_real)
        tolerance = relative_tolerance(earth[variable], target)
        spec = specs[body]
        index = spec.index[spec["base_id"] == base_id]
        if len(index) != 1:
            raise ValueError(f"Base {base_id} não encontrada em {body}.parquet")
        target_column = f"{variable}__alvo"
        if target_column not in spec.columns:
            raise ValueError(f"{target_column} não existe em {body}.parquet")
        tolerance_column = f"{variable}{TOLERANCE_SUFFIX}"
        if tolerance_column not in spec.columns:
            spec[tolerance_column] = np.nan
        spec.loc[index, target_column] = target
        spec.loc[index, tolerance_column] = tolerance
        mask = ((catalog["corpo"] == body) & (catalog["base_id"] == base_id)
                & (catalog["terra"] == variable))
        if not mask.any():
            raise ValueError(f"{body}/{base_id}/{variable} não está no catálogo")
        catalog.loc[mask, "alvo"] = target
        catalog.loc[mask, "regra_alvo"] = f"valor real ({row.confianca}): {row.fonte}"
        catalog.loc[mask, "tolerancia"] = tolerance
        catalog.loc[mask, "regra_tolerancia"] = TOLERANCE_RULE
    for spec in specs.values():
        spec["status"] = STATUS
    return specs, catalog


def main() -> None:
    inputs, _ = load_inputs(ROOT)
    real = pd.read_csv(REAL_VALUES)
    references = {body: pd.read_parquet(ROOT / "data" / body / f"{body}.parquet")
                  for body in ("lua", "marte")}
    catalog = pd.read_csv(CATALOG, encoding="utf-8-sig")
    specs, catalog = apply_real_values(real, inputs.earth, references, catalog)
    for body, spec in specs.items():
        spec.to_parquet(ROOT / "data" / body / f"{body}.parquet", index=False)
    catalog.to_csv(CATALOG, index=False, encoding="utf-8-sig")
    print(f"{len(real)} alvos reais aplicados em {len(specs)} corpos")
    print(real.groupby(["corpo", "confianca"]).size().to_string())


if __name__ == "__main__":
    main()
