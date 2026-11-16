"""Backtest rolling-origin: sazonal × LightGBM direto/recursivo e estabilidade do ranking.

Para cada corte simulado ``c`` (meses observados com 12 meses de futuro conhecido):

1. treina modelos LightGBM padrão (100 árvores) por variável e horizonte H1–H3 só
   com destinos ``<= c`` (sem rótulos posteriores ao corte);
2. projeta ``c+1 … c+12`` com o mesmo motor da API (diretos até H3, recursivo depois),
   alimentando os passos seguintes com as próprias previsões;
3. compara com o observado e com o sazonal (mesmo mês do ano anterior), nas mesmas
   linhas válidas: MAE, RMSE, viés e ganho de MAE sobre o sazonal;
4. compara o top K de cada base (nicho Todos) calculado com o estado projetado e
   com o observado do mesmo mês (sobreposição do top K).

Uso:  python scripts/avaliar_projecoes.py --prefixo-csv avaliacao_analogos
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from lightgbm import LGBMRegressor  # noqa: E402

from feynmans_legacy.analog_study import (  # noqa: E402
    FEATURES,
    forecast_design,
    profile_criteria,
    recommend,
)
from feynmans_legacy.forecast_projection import (  # noqa: E402
    ProjectionBundle,
    TrajectoryStore,
    observed_window,
    period,
    project_until,
    to_anomes,
)

RUN = ROOT / "data/terra/analise_analogos"
HORIZONS_REPORTED = (1, 3, 6, 12)
DIRECT = (1, 2, 3)


def gain(model_mae: float, baseline_mae: float) -> float:
    """Percent MAE reduction over the seasonal baseline (positive = better)."""
    return 100 * (baseline_mae - model_mae) / baseline_mae if baseline_mae > 0 else np.nan


def train_bundle(history: pd.DataFrame, variables: list[str], cutoff: pd.Period,
                 seed: int) -> ProjectionBundle:
    models: dict[tuple[str, int], object] = {}
    for variable in variables:
        for horizon in DIRECT:
            design = forecast_design(history, variable, horizon).dropna(subset=["observado"])
            train = design[design["destino"] <= cutoff]
            if len(train) < 20:
                continue
            model = LGBMRegressor(n_estimators=100, learning_rate=0.1, num_leaves=31,
                                  random_state=seed, n_jobs=4, verbosity=-1)
            models[(variable, horizon)] = model.fit(train[FEATURES], train["observado"])
    return ProjectionBundle(cutoff, models, f"backtest-{cutoff}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefixo-csv", default="avaliacao_analogos")
    parser.add_argument("--locais", type=int, default=400)
    parser.add_argument("--cortes", type=int, default=3)
    parser.add_argument("--espaco-meses", type=int, default=6)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args()
    started = time.perf_counter()
    selection = json.loads((RUN / "selecao.json").read_text(encoding="utf-8"))
    variables = list(selection["alvos_previsao"])
    coords = pd.read_parquet(RUN / "coordenadas.parquet")
    coords["location_id"] = coords["location_id"].astype(str)
    sample = coords.sample(n=min(args.locais, len(coords)), random_state=args.semente)
    ids = pd.Index(sorted(sample["location_id"]), name="location_id")
    terra = pd.read_parquet(ROOT / "data/terra/terra.parquet",
                            columns=["location_id", "anomes", *variables],
                            filters=[("location_id", "in", list(ids))])
    terra["location_id"] = terra["location_id"].astype(str)
    static = pd.read_parquet(RUN / "estaticas.parquet")
    static["location_id"] = static["location_id"].astype(str)
    last = period(int(terra["anomes"].max()))
    cutoffs = [last - 12 - args.espaco_meses * i for i in range(args.cortes)]
    references = {b: pd.read_parquet(ROOT / "data" / b / f"{b}.parquet")
                  for b in ("lua", "marte")}
    niches = ROOT / "config/nichos.json"
    errors, rankings = [], []
    for cutoff in cutoffs:
        history = terra[terra["anomes"] <= to_anomes(cutoff)]
        bundle = train_bundle(history, variables, cutoff, args.semente)
        with TemporaryDirectory() as tmp:
            store = TrajectoryStore(Path(tmp), "bt")
            project_until(cutoff + 12, bundle, store,
                          lambda h=history, c=cutoff: observed_window(h, c, ids, variables),
                          variables)
            for horizon in range(1, 13):
                month = cutoff + horizon
                projected = store.read(month)
                observed = (terra[terra["anomes"] == to_anomes(month)]
                            .set_index("location_id").reindex(ids))
                seasonal = (terra[terra["anomes"] == to_anomes(month - 12)]
                            .set_index("location_id").reindex(ids))
                methods = store.months_index()[str(to_anomes(month))]["metodos"]
                for variable in variables:
                    y = observed[variable].to_numpy(dtype=float)
                    p = projected[variable].to_numpy(dtype=float)
                    s = seasonal[variable].to_numpy(dtype=float)
                    ok = np.isfinite(y) & np.isfinite(p) & np.isfinite(s)
                    if not ok.any():
                        continue
                    errors.append({
                        "corte": to_anomes(cutoff), "horizonte": horizon,
                        "variavel": variable, "metodo": methods[variable],
                        "n": int(ok.sum()),
                        "mae_modelo": float(np.mean(np.abs(p[ok] - y[ok]))),
                        "rmse_modelo": float(np.sqrt(np.mean((p[ok] - y[ok]) ** 2))),
                        "vies_modelo": float(np.mean(p[ok] - y[ok])),
                        "mae_sazonal": float(np.mean(np.abs(s[ok] - y[ok]))),
                    })
                if horizon not in HORIZONS_REPORTED:
                    continue
                state = {
                    "projetado": static.merge(projected.reset_index(), on="location_id"),
                    "observado": static.merge(observed.reset_index().drop(
                        columns="anomes"), on="location_id"),
                }
                for body, reference in references.items():
                    for base_id in reference["base_id"]:
                        criteria = profile_criteria(niches, body, "Todos", reference, base_id)
                        tops = {}
                        for name, frame in state.items():
                            cols = [c for c in criteria if c in frame.columns]
                            ranked = recommend(frame[["location_id", *cols]], coords,
                                               {c: criteria[c] for c in cols})
                            tops[name] = ranked["location_id"].head(args.k).tolist()
                        overlap = len(set(tops["projetado"]) & set(tops["observado"]))
                        rankings.append({
                            "corte": to_anomes(cutoff), "horizonte": horizon,
                            "base_id": base_id, "k": args.k,
                            "acordo_top_k": overlap / args.k,
                            "mesmo_top1": tops["projetado"][:1] == tops["observado"][:1],
                        })
        print(f"corte {cutoff}: ok ({time.perf_counter() - started:.0f} s)", flush=True)
    errors_frame = pd.DataFrame(errors)
    errors_frame["ganho_mae_pct"] = [gain(m, s) for m, s in zip(
        errors_frame["mae_modelo"], errors_frame["mae_sazonal"], strict=True)]
    ranking_frame = pd.DataFrame(rankings)
    out = RUN / "avaliacao"
    out.mkdir(exist_ok=True)
    errors_frame.to_csv(out / f"{args.prefixo_csv}_erros.csv", index=False)
    ranking_frame.to_csv(out / f"{args.prefixo_csv}_ranking.csv", index=False)
    summary = pd.DataFrame({
        "ganho_mae_mediano_pct": errors_frame[errors_frame["horizonte"].isin(
            HORIZONS_REPORTED)].groupby("horizonte")["ganho_mae_pct"].median(),
        "acordo_top_k_medio": ranking_frame.groupby("horizonte")["acordo_top_k"].mean(),
        "mesmo_top1": ranking_frame.groupby("horizonte")["mesmo_top1"].mean(),
    }).round(4)
    summary.to_csv(out / f"{args.prefixo_csv}_resumo.csv")
    print(summary.to_string())
    print(f"locais={len(ids)} variaveis={len(variables)} cortes={[str(c) for c in cutoffs]} "
          f"tempo={time.perf_counter() - started:.0f}s")
    print(f"Arquivos em {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
