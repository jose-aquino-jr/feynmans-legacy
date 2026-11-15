"""Tune monthly LightGBM forecasts and evaluate an untouched temporal holdout."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypedDict

import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMRegressor
from lightgbm import __version__ as lightgbm_version
from optuna.trial import Trial
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)

from .analog_study import FEATURES, ForecastBundle, forecast_design, months


class Params(TypedDict, total=False):
    max_depth: int
    num_leaves: int
    n_estimators: int
    learning_rate: float
    min_child_samples: int
    reg_alpha: float
    reg_lambda: float
    subsample: float
    subsample_freq: int
    colsample_bytree: float


DEFAULT_PARAMS: Params = {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31}


@dataclass
class HorizonSplit:
    horizon: int
    train: pd.DataFrame
    validation: list[tuple[pd.DataFrame, pd.DataFrame]]
    test: pd.DataFrame


def _fit(frame: pd.DataFrame, params: Params, seed: int) -> LGBMRegressor:
    model = LGBMRegressor(**params, random_state=seed, n_jobs=4, verbosity=-1)
    model.fit(frame[FEATURES], frame["observado"])
    return model


def _validation_mae(
    windows: list[tuple[pd.DataFrame, pd.DataFrame]], params: Params | None, seed: int,
) -> float:
    errors = []
    for train, holdout in windows:
        prediction = (
            holdout["lag_0"] if params is None
            else _fit(train, params, seed).predict(holdout[FEATURES])
        )
        errors.append(mean_absolute_error(holdout["observado"], prediction))
    return float(np.mean(errors))


def _suggest(trial: Trial) -> Params:
    depth = trial.suggest_int("max_depth", 3, 8)
    return {
        "max_depth": depth,
        "num_leaves": trial.suggest_int("num_leaves", 4, min(64, 2**depth)),
        "n_estimators": trial.suggest_int("n_estimators", 60, 220, step=20),
        "learning_rate": trial.suggest_float("learning_rate", 0.025, 0.15, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 25, 200, step=5),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-5, 10, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 20, log=True),
        "subsample": trial.suggest_float("subsample", 0.7, 1.0),
        "subsample_freq": 1,
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.65, 1.0),
    }


def _optimize(
    splits: list[HorizonSplit], n_trials: int, seed: int,
) -> tuple[Params, list[float], list[float], optuna.Study]:
    defaults = [_validation_mae(split.validation, DEFAULT_PARAMS, seed) for split in splits]

    def objective(trial: Trial) -> float:
        params = _suggest(trial)
        losses = [_validation_mae(split.validation, params, seed) for split in splits]
        trial.set_user_attr("mae_por_horizonte", losses)
        trial.set_user_attr("parametros_completos", params)
        return float(np.mean(losses))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    if study.best_value >= float(np.mean(defaults)):
        return DEFAULT_PARAMS, defaults, defaults, study
    return (
        study.best_trial.user_attrs["parametros_completos"],
        study.best_trial.user_attrs["mae_por_horizonte"],
        defaults,
        study,
    )


def _test_metrics(split: HorizonSplit, predicted: np.ndarray, validation_end: pd.Period,
                  ) -> dict[str, object]:
    test = split.test
    observed = test["observado"]
    threshold = split.train["observado"].quantile(0.90)
    events = observed > threshold
    estimated = predicted > threshold
    operational = test["origem"] >= validation_end
    return {
        "n_teste": len(test),
        "mae_teste": mean_absolute_error(observed, predicted),
        "rmse_teste": root_mean_squared_error(observed, predicted),
        "n_teste_operacional": int(operational.sum()),
        "mae_teste_operacional": (
            mean_absolute_error(observed[operational], predicted[operational.to_numpy()])
            if operational.any() else None
        ),
        "p90_treino": threshold,
        "eventos_teste": int(events.sum()),
        "f1_teste": f1_score(events, estimated, zero_division=0),
        "recall_teste": recall_score(events, estimated, zero_division=0),
        "precisao_teste": precision_score(events, estimated, zero_division=0),
        "roc_auc_teste": roc_auc_score(events, predicted) if events.nunique() == 2 else None,
    }


def train_forecasts(
    history: pd.DataFrame,
    variables: Iterable[str],
    horizons: Sequence[int],
    *,
    n_trials: int = 24,
    seed: int = 42,
    min_rows: int = 20,
) -> tuple[ForecastBundle, pd.DataFrame, dict[str, object]]:
    """Tune on two target months, test on three, then refit for publication."""
    if n_trials < 1 or not horizons or any(h < 1 for h in horizons):
        raise ValueError("Informe tentativas positivas e pelo menos um horizonte mensal válido.")
    periods = sorted(months(history["anomes"]).unique())
    if len(periods) <= 5:
        raise ValueError("São necessários meses de treino além dos cinco meses reservados.")
    train_end = periods[-6]
    val_months = periods[-5:-3]
    test_months = periods[-3:]
    if list(pd.period_range(train_end, periods[-1], freq="M")) != periods[-6:]:
        raise ValueError("Os cinco meses reservados precisam seguir o último mês de treino.")
    models: dict[tuple[str, int], LGBMRegressor | None] = {}
    metrics: list[dict[str, object]] = []
    studies: dict[str, object] = {}
    audit: dict[str, object] = {
        "treino_inicio": str(periods[0]),
        "treino_fim": str(train_end),
        "validacao": [str(month) for month in val_months],
        "teste": [str(month) for month in test_months],
        "n_trials_por_variavel": n_trials,
        "semente": seed,
        "optuna": optuna.__version__,
        "lightgbm": lightgbm_version,
        "estudos": studies,
    }
    for variable in variables:
        splits = []
        designs = {}
        for horizon in horizons:
            labeled = forecast_design(history, variable, horizon).dropna(subset=["observado"])
            train = labeled.loc[labeled["destino"] <= train_end]
            windows = [
                (
                    train.loc[train["destino"] <= month - horizon],
                    labeled.loc[labeled["destino"] == month],
                )
                for month in val_months
            ]
            test = labeled.loc[labeled["destino"].isin(test_months)]
            if any(len(frame) < min_rows for pair in windows for frame in pair) or test.empty:
                metrics.append({"variavel": variable, "horizonte": horizon,
                                "status": "historico insuficiente"})
                continue
            splits.append(HorizonSplit(horizon, train, windows, test))
            designs[horizon] = labeled
        if not splits:
            continue

        params, val_maes, defaults, study = _optimize(splits, n_trials, seed)
        studies[variable] = {
            "horizontes": [split.horizon for split in splits],
            "parametros_selecionados": params,
            "mae_validacao_padrao": defaults,
            "mae_validacao_selecionado": val_maes,
            "tentativas": [
                {
                    "numero": trial.number,
                    "mae_validacao": trial.value,
                    **trial.user_attrs,
                }
                for trial in study.trials
            ],
        }
        for split, val_mae, default_mae in zip(splits, val_maes, defaults, strict=True):
            horizon = split.horizon
            # Longer leads can originate before the frozen training cutoff.
            if (split.test["origem"] < train_end).any():
                raise ValueError(f"Horizonte {horizon} excede a janela de teste congelada.")
            n_validation = sum(len(holdout) for _, holdout in split.validation)
            baseline_mae = _validation_mae(split.validation, None, seed)
            method = "lightgbm" if val_mae < baseline_mae else "persistencia"
            features = split.test[FEATURES]
            observed = split.test["observado"]
            persistence = split.test["lag_0"].to_numpy()
            tuned = _fit(split.train, params, seed).predict(features)
            default = tuned if params == DEFAULT_PARAMS else (
                _fit(split.train, DEFAULT_PARAMS, seed).predict(features)
            )
            selected = tuned if method == "lightgbm" else persistence
            metrics.append({
                "variavel": variable, "horizonte": horizon, "status": method,
                "configuracao": "padrao" if params == DEFAULT_PARAMS else "optuna",
                "n_treino": len(split.train), "n_validacao": n_validation,
                **{f"n_teste_{month.strftime('%Y%m')}": int(split.test["destino"].eq(month).sum())
                   for month in test_months},
                "mae_modelo": val_mae, "mae_validacao_padrao": default_mae,
                "mae_persistencia": baseline_mae,
                "mae_teste_modelo": mean_absolute_error(observed, tuned),
                "mae_teste_padrao": mean_absolute_error(observed, default),
                "mae_teste_persistencia": mean_absolute_error(observed, persistence),
                **_test_metrics(split, selected, val_months[-1]),
            })
            models[(variable, horizon)] = (
                _fit(designs[horizon], params, seed) if method == "lightgbm" else None
            )
    return {"origem": str(periods[-1]), "modelos": models}, pd.DataFrame(metrics), audit
