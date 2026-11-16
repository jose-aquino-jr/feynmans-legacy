"""Projeção mensal da Terra a partir do pacote LightGBM, com extensão recursiva.

Contrato do pacote (``train_forecasts``): ``{"origem": "AAAA-MM", "modelos": {(var, h): m}}``.
``m`` é um ``LGBMRegressor`` ou ``None`` (persistência explícita: ``lag_0``); a ausência
da chave significa que não há modelo para aquele par. As features são ``lag_0, lag_1,
lag_2, lag_11`` (meses de calendário antes da origem) e seno/cosseno do mês de destino,
nessa ordem (``FEATURES``).

Para cada mês ``t`` depois do corte ``c`` e cada variável, usa o maior horizonte direto
``h`` com modelo e ``h <= t - c``; a origem das features é ``t - h``. Os lags vêm das
observações (até ``c``) ou de valores já projetados no mesmo ID. Sem horizonte que
caiba, usa o mesmo mês do ano anterior (``t - 12``) e declara o método. Lags ausentes
geram valor nulo, contado por variável.

Os valores são mantidos em ``float32`` do começo ao fim, para que retomar de um
checkpoint em disco seja idêntico a rodar do zero.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analog_study import FEATURES, LAGS

ALGORITHM_VERSION = "recursiva-v1"
SCHEMA_VERSION = 1
DTYPE = np.float32
WINDOW_MONTHS = 15
SEASONAL_LAG = 12
STRATEGIES = ("recursiva", "auto", "sazonal")
ORIGINS = ("observada", "prevista", "extrapolada", "cenario_sazonal")
BATCH_SIZE = 50_000


def period(anomes: int | str | pd.Period) -> pd.Period:
    """``202608``, ``"2026-08"`` or a monthly Period → monthly Period (strict)."""
    if isinstance(anomes, pd.Period):
        return anomes.asfreq("M")
    text = str(anomes)
    if text.isdigit() and len(text) == 6:
        month = int(text[4:])
        if not 1 <= month <= 12:
            raise ValueError(f"Mês inválido em {anomes}.")
        return pd.Period(year=int(text[:4]), month=month, freq="M")
    return pd.Period(text, freq="M")


def to_anomes(month: pd.Period) -> int:
    return int(month.strftime("%Y%m"))


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ProjectionBundle:
    cutoff: pd.Period
    models: Mapping[tuple[str, int], Any]
    sha256: str = ""

    @property
    def variables(self) -> list[str]:
        return sorted({variable for variable, _ in self.models})

    def horizons(self, variable: str) -> list[int]:
        return sorted(h for v, h in self.models if v == variable)

    @property
    def max_horizon(self) -> int:
        return max((h for _, h in self.models), default=0)


def load_bundle(path: str | Path) -> ProjectionBundle:
    """Load a trusted, operator-configured pickle and check its contract."""
    file = Path(path)
    with file.open("rb") as handle:
        raw = pickle.load(handle)  # noqa: S301 - only from the configured publication
    if not isinstance(raw, dict) or "origem" not in raw or "modelos" not in raw:
        raise ValueError("Pacote de previsão sem 'origem' e 'modelos'.")
    models = raw["modelos"]
    for key, model in models.items():
        if (not isinstance(key, tuple) or len(key) != 2 or not isinstance(key[1], int)
                or key[1] < 1):
            raise ValueError(f"Chave de modelo inválida: {key!r}")
        if model is not None and not hasattr(model, "predict"):
            raise ValueError(f"Modelo sem predict em {key!r}")
    return ProjectionBundle(period(raw["origem"]), dict(models), file_sha256(file))


def choose_horizon(available: Sequence[int], step: int) -> int | None:
    """Largest direct horizon with a model that fits ``step`` months after the cutoff."""
    fitting = [h for h in available if h <= step]
    return max(fitting) if fitting else None


def method_label(horizon: int | None, model: Any) -> str:
    if horizon is None:
        return "sazonal_t-12"
    return f"persistencia_h{horizon}" if model is None else f"lightgbm_h{horizon}"


Window = dict[pd.Period, pd.DataFrame]


def month_values(window: Window, month: pd.Period, variable: str,
                 ids: pd.Index) -> np.ndarray:
    frame = window.get(month)
    if frame is None or variable not in frame.columns:
        return np.full(len(ids), np.nan, dtype=DTYPE)
    return frame[variable].to_numpy(dtype=DTYPE)


def project_month(
    window: Window, target: pd.Period, bundle: ProjectionBundle, ids: pd.Index,
    variables: Sequence[str], batch_size: int = BATCH_SIZE,
) -> tuple[pd.DataFrame, dict[str, str], dict[str, int]]:
    """One projected month for every ID: values, method per variable, nulls per variable."""
    step = (target - bundle.cutoff).n
    phase = target.month * (2 * np.pi / 12)
    columns: dict[str, np.ndarray] = {}
    methods: dict[str, str] = {}
    nulls: dict[str, int] = {}
    for variable in variables:
        horizon = choose_horizon(bundle.horizons(variable), step)
        if horizon is None:
            values = month_values(window, target - SEASONAL_LAG, variable, ids)
            model = None
        else:
            model = bundle.models[(variable, horizon)]
            origin = target - horizon
            lags = np.column_stack([month_values(window, origin - lag, variable, ids)
                                    for lag in LAGS])
            values = np.full(len(ids), np.nan, dtype=DTYPE)
            valid = np.isfinite(lags).all(axis=1)
            if model is None:
                values[valid] = lags[valid, 0]
            elif valid.any():
                features = np.column_stack([
                    lags, np.full(len(ids), np.sin(phase)), np.full(len(ids), np.cos(phase)),
                ])
                rows = np.flatnonzero(valid)
                for start in range(0, len(rows), batch_size):
                    chunk = rows[start:start + batch_size]
                    frame = pd.DataFrame(features[chunk], columns=FEATURES)
                    values[chunk] = np.asarray(model.predict(frame), dtype=DTYPE)
        values = np.where(np.isfinite(values), values, np.nan).astype(DTYPE)
        columns[variable] = values
        methods[variable] = method_label(horizon, model)
        nulls[variable] = int(np.isnan(values).sum())
    return pd.DataFrame(columns, index=ids), methods, nulls


def observed_window(history: pd.DataFrame, cutoff: pd.Period, ids: pd.Index,
                    variables: Sequence[str]) -> Window:
    """Observed months ``cutoff - 14 … cutoff`` as ID × variable frames (gaps = NaN)."""
    codes = history["anomes"].astype(int).to_numpy()
    window: Window = {}
    for offset in range(WINDOW_MONTHS - 1, -1, -1):
        month = cutoff - offset
        rows = history[codes == to_anomes(month)].set_index("location_id")
        frame = rows.reindex(ids)[list(variables)] if not rows.empty else pd.DataFrame(
            np.nan, index=ids, columns=list(variables))
        window[month] = frame.astype(DTYPE)
    return window


@dataclass
class TrajectoryStore:
    """Projected months on disk: ``<root>/<key>/<AAAAMM>.parquet`` + ``meses.json``."""

    root: Path
    key: str
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def folder(self) -> Path:
        return self.root / self.key

    def path(self, month: pd.Period) -> Path:
        return self.folder / f"{to_anomes(month)}.parquet"

    def has(self, month: pd.Period) -> bool:
        return self.path(month).is_file()

    def read(self, month: pd.Period) -> pd.DataFrame:
        frame = pd.read_parquet(self.path(month))
        return frame.set_index("location_id")

    def write(self, month: pd.Period, frame: pd.DataFrame, methods: Mapping[str, str],
              nulls: Mapping[str, int]) -> None:
        """Atomic write: data first, then the month entry in ``meses.json``."""
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.path(month)
        temporary = target.with_suffix(".parquet.tmp")
        frame.reset_index(names="location_id").to_parquet(temporary, index=False)
        os.replace(temporary, target)
        index = self.months_index()
        index[str(to_anomes(month))] = {"metodos": dict(methods), "nulos": dict(nulls)}
        self._write_json("meses.json", index)

    def months_index(self) -> dict[str, Any]:
        path = self.folder / "meses.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def write_manifest(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self._write_json("manifesto.json", self.meta)

    def _write_json(self, name: str, payload: Any) -> None:
        path = self.folder / name
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        os.replace(temporary, path)

    def last_contiguous(self, cutoff: pd.Period) -> pd.Period:
        """Last month ``m`` such that every month in ``(cutoff, m]`` is stored and indexed."""
        index = self.months_index()
        month = cutoff
        while str(to_anomes(month + 1)) in index and self.has(month + 1):
            month += 1
        return month


def trajectory_key(bundle_sha: str, history_sha: str,
                   variables: Iterable[str]) -> str:
    payload = json.dumps({
        "bundle": bundle_sha, "historico": history_sha, "estrategia": "recursiva",
        "algoritmo": ALGORITHM_VERSION, "esquema": SCHEMA_VERSION,
        "variaveis": sorted(variables),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


ProgressCallback = Callable[[pd.Period, int, int, bool], None]


def project_until(
    target: pd.Period,
    bundle: ProjectionBundle,
    store: TrajectoryStore,
    load_observed: Callable[[], Window],
    variables: Sequence[str],
    *,
    progress: ProgressCallback | None = None,
    should_extend: Callable[[], pd.Period] | None = None,
    batch_size: int = BATCH_SIZE,
) -> pd.Period:
    """Project month by month until ``target``, resuming from the stored checkpoint.

    ``should_extend`` lets a running job learn about a later destination requested
    meanwhile. Returns the last month materialized.
    """
    cutoff = bundle.cutoff
    if target <= cutoff:
        return cutoff
    store.write_manifest()
    done = store.last_contiguous(cutoff)
    window = load_observed()
    ids = next(iter(window.values())).index
    # Rebuild the moving window from stored months (checkpoint) when resuming.
    for offset in range(WINDOW_MONTHS - 1, -1, -1):
        month = done - offset
        if month > cutoff:
            window[month] = store.read(month).reindex(ids)[list(variables)].astype(DTYPE)
    goal = target
    month = done
    total = (goal - cutoff).n
    while month < goal:
        month += 1
        frame, methods, nulls = project_month(window, month, bundle, ids, variables,
                                              batch_size)
        store.write(month, frame, methods, nulls)
        window[month] = frame
        for old in [m for m in window if m < month - (WINDOW_MONTHS - 1)]:
            del window[old]
        if should_extend is not None:
            goal = max(goal, should_extend())
            total = (goal - cutoff).n
        if progress is not None:
            progress(month, (month - cutoff).n, total, False)
    return month


def origin_for(month: pd.Period, cutoff: pd.Period, max_horizon: int, strategy: str,
               observed: set[pd.Period]) -> str:
    """Contract label of the Earth state used for ``month``."""
    if month <= cutoff:
        return "observada"
    if strategy == "sazonal":
        return "cenario_sazonal"
    if (month - cutoff).n <= max_horizon:
        return "prevista"
    return "extrapolada" if strategy == "recursiva" else "cenario_sazonal"


def seasonal_base(month: pd.Period, cutoff: pd.Period) -> pd.Period:
    """Same calendar month in the last observed year (scenario reference)."""
    base = pd.Period(year=cutoff.year, month=month.month, freq="M")
    return base if base <= cutoff else base - 12
