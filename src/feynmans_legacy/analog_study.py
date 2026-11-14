"""Shared preparation, monthly forecasting and ranking for the study notebooks."""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

KEY = ["location_id", "anomes"]
LAGS = [0, 1, 2, 11]
FEATURES = [f"lag_{lag}" for lag in LAGS] + ["month_sin", "month_cos"]


def months(values):
    """Parse strict YYYYMM into monthly periods."""
    return pd.to_datetime(values.astype(str), format="%Y%m", errors="raise").dt.to_period("M")


def validate_key(frame, key, name):
    if frame[key].isna().any().any() or frame.duplicated(key).any():
        raise ValueError(f"{name}: chave nula ou duplicada em {key}")


def select_features(snapshot, candidates, min_coverage=0.8, max_correlation=0.9):
    rows, selected = [], []
    for name in candidates:
        coverage = snapshot[name].notna().mean()
        reason = "selecionada"
        if coverage < min_coverage:
            reason = "cobertura insuficiente"
        elif snapshot[name].nunique() < 2:
            reason = "sem variacao"
        else:
            redundant = [column for column in selected
                         if abs(snapshot[name].corr(snapshot[column])) >= max_correlation]
            if redundant:
                reason = f"correlacao com {redundant[0]}"
            else:
                selected.append(name)
        rows.append({"variavel": name, "cobertura": coverage, "decisao": reason})
    return selected, pd.DataFrame(rows)


def cluster_snapshot(snapshot, features, n_clusters):
    complete = snapshot.dropna(subset=features)
    if not features or len(complete[features].drop_duplicates()) < n_clusters:
        raise ValueError("Amostra insuficiente para a quantidade de clusters solicitada.")
    model = make_pipeline(StandardScaler(), KMeans(n_clusters=n_clusters, random_state=42))
    result = snapshot[KEY].copy()
    result["cluster"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result.loc[complete.index, "cluster"] = model.fit_predict(complete[features])
    return result


def forecast_design(history, variable, horizon):
    # Join on actual calendar months so gaps never become artificial lags.
    source = history[KEY + [variable]].dropna().copy()
    source["anomes"] = months(source["anomes"])
    design = source[KEY].rename(columns={"anomes": "origem"}).copy()
    design["destino"] = design["origem"] + horizon
    for lag in LAGS:
        values = source.rename(columns={"anomes": "origem", variable: f"lag_{lag}"})
        values["origem"] += lag
        design = design.merge(values, on=["location_id", "origem"], how="left")
    target = source.rename(columns={"anomes": "destino", variable: "observado"})
    design = design.merge(target, on=["location_id", "destino"], how="left")
    phase = design["destino"].dt.month * (2 * np.pi / 12)
    design["month_sin"], design["month_cos"] = np.sin(phase), np.cos(phase)
    return design.dropna(subset=FEATURES)


def train_forecasts(history, variables, horizons, min_validation=20):
    """Select model or persistence by MAE on a chronological holdout."""
    latest = months(history["anomes"]).max()
    origins = sorted(months(history["anomes"]).unique())
    cutoff = origins[int(len(origins) * 0.8)]
    models, metrics = {}, []
    for variable in variables:
        for horizon in horizons:
            design = forecast_design(history, variable, horizon)
            labeled = design.dropna(subset=["observado"])
            train = labeled[labeled["destino"] <= cutoff]
            validation = labeled[labeled["origem"] >= cutoff]
            if len(train) < min_validation or len(validation) < min_validation:
                metrics.append({"variavel": variable, "horizonte": horizon,
                                "status": "historico insuficiente"})
                continue
            estimator = RandomForestRegressor(
                n_estimators=80, min_samples_leaf=5, random_state=42, n_jobs=-1
            )
            estimator.fit(train[FEATURES], train["observado"])
            predicted = estimator.predict(validation[FEATURES])
            mae_model = (validation["observado"] - predicted).abs().mean()
            mae_baseline = (validation["observado"] - validation["lag_0"]).abs().mean()
            method = "random_forest" if mae_model < mae_baseline else "persistencia"
            models[(variable, horizon)] = (
                estimator.fit(labeled[FEATURES], labeled["observado"]) if method == "random_forest"
                else None
            )
            metrics.append({"variavel": variable, "horizonte": horizon, "status": method,
                            "n_validacao": len(validation), "mae_modelo": mae_model,
                            "mae_persistencia": mae_baseline})
    return {"origem": str(latest), "modelos": models}, pd.DataFrame(metrics)


def publish_forecasts(history, model_path):
    """Load a trusted artifact produced by train_forecasts and predict in batch."""
    with Path(model_path).open("rb") as file:
        bundle = pickle.load(file)
    latest = months(history["anomes"]).max()
    if str(latest) != bundle["origem"]:
        raise ValueError("O historico precisa terminar no mesmo anomes do artefato.")
    output = []
    for (variable, horizon), model in bundle["modelos"].items():
        design = forecast_design(history, variable, horizon)
        future = design.loc[design["origem"] == latest].copy()
        if future.empty:
            continue
        future["valor_previsto"] = (
            future["lag_0"] if model is None else model.predict(future[FEATURES])
        )
        future["anomes"] = future["destino"].dt.strftime("%Y%m").astype(int)
        future["variavel"] = variable
        output.append(future[KEY + ["variavel", "valor_previsto"]])
    columns = KEY + ["variavel", "valor_previsto"]
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame(columns=columns)


def profile_criteria(niches_path, body, niche, reference, base_id):
    """Resolve one row of a fixed reference spec and its mapped Earth criteria."""
    config = json.loads(Path(niches_path).read_text(encoding="utf-8"))
    entries = config[body]
    if niche != "Todos":
        entries = {niche: entries[niche]}
    validate_key(reference, ["base_id"], body)
    row = reference.set_index("base_id").loc[base_id]
    criteria = {}
    for mappings in entries.values():
        for item in mappings:
            earth_column = item["terra"]
            target = float(row[item["referencia"]])
            tolerance, weight = float(item["tolerancia"]), float(item.get("peso", 1))
            if not np.isfinite([target, tolerance, weight]).all() or min(tolerance, weight) <= 0:
                raise ValueError(f"Alvo, tolerancia ou peso invalido para {earth_column}")
            values = (target, tolerance, weight)
            if earth_column in criteria and criteria[earth_column] != values:
                raise ValueError(f"Criterios divergentes para {earth_column} em Todos")
            criteria[earth_column] = values
    if not criteria:
        raise ValueError("O perfil selecionado nao tem criterios.")
    return criteria


def recommend(values, coordinates, criteria):
    validate_key(values, ["location_id"], "consulta")
    validate_key(coordinates, ["location_id"], "coordenadas")
    missing = set(criteria).difference(values.columns)
    if missing:
        raise ValueError(f"Criterios sem dados no periodo: {sorted(missing)}")
    ranked = values.dropna(subset=list(criteria)).copy()
    ranked = ranked.merge(coordinates[["location_id", "latitude", "longitude"]],
                          on="location_id", how="left", validate="one_to_one")
    valid_coordinates = (
        ranked["latitude"].between(-90, 90) & ranked["longitude"].between(-180, 180)
    )
    ranked = ranked[valid_coordinates].copy()
    weight_sum = sum(weight for _, _, weight in criteria.values())
    ranked["nota"] = 0.0
    for variable, (target, tolerance, weight) in criteria.items():
        ranked[f"alvo_{variable}"] = target
        relative_error = (ranked[variable] - target).abs() / tolerance
        ranked[f"nota_{variable}"] = 100 * (1 - relative_error).clip(lower=0)
        ranked[f"peso_{variable}"] = weight / weight_sum
        ranked["nota"] += ranked[f"nota_{variable}"] * weight / weight_sum
    return ranked.sort_values(["nota", "location_id"], ascending=[False, True])
