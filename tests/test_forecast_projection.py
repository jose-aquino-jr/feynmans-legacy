"""Testes do motor de projeção mensal recursiva (fixtures determinísticas)."""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from feynmans_legacy.forecast_projection import (
    ProjectionBundle,
    TrajectoryStore,
    choose_horizon,
    load_bundle,
    observed_window,
    origin_for,
    period,
    project_month,
    project_until,
    seasonal_base,
    to_anomes,
)

VAR = "temperatura__ar_2m_c"
NDVI = "biologia__ndvi"


class PlusOne:
    """lag_0 + 1: shows exactly which origin month fed the prediction."""

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return frame["lag_0"].to_numpy() + 1


class MonthCosine:
    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return frame["month_cos"].to_numpy()


def history(cutoff: str = "2026-08", ids: tuple[str, ...] = ("T001", "T002")) -> pd.DataFrame:
    end = pd.Period(cutoff, freq="M")
    rows = []
    for offset in range(20):
        month = end - offset
        for index, location in enumerate(ids):
            rows.append({"location_id": location, "anomes": to_anomes(month),
                         VAR: 10.0 * (index + 1) + offset, NDVI: 0.1 * (offset % 12)})
    return pd.DataFrame(rows)


def bundle(models: dict[tuple[str, int], object], cutoff: str = "2026-08") -> ProjectionBundle:
    return ProjectionBundle(pd.Period(cutoff, freq="M"), models, "sha")


def window_for(frame: pd.DataFrame, cutoff: str = "2026-08") -> dict[pd.Period, pd.DataFrame]:
    ids = pd.Index(sorted(frame["location_id"].unique()), name="location_id")
    return observed_window(frame, pd.Period(cutoff, freq="M"), ids, [VAR, NDVI])


def run(
    models: dict[tuple[str, int], object], target: str, tmp: Path,
    frame: pd.DataFrame | None = None, cutoff: str = "2026-08", **kwargs: object,
) -> TrajectoryStore:
    data = history(cutoff) if frame is None else frame
    store = TrajectoryStore(tmp, "t")
    project_until(period(target), bundle(models, cutoff), store, lambda: window_for(data, cutoff),
                  [VAR, NDVI], **kwargs)  # type: ignore[arg-type]
    return store


def test_period_parsing_and_validation() -> None:
    assert period(204007) == pd.Period("2040-07", freq="M")
    assert period("2026-08") == pd.Period("2026-08", freq="M")
    with pytest.raises(ValueError):
        period(202613)
    assert (period(204007) - period(202608)).n == 167


def test_choose_largest_fitting_horizon() -> None:
    assert choose_horizon([1, 2, 3], 1) == 1
    assert choose_horizon([1, 2, 3], 2) == 2
    assert choose_horizon([1, 2, 3], 40) == 3
    assert choose_horizon([3], 2) is None
    assert choose_horizon([], 5) is None


def test_estimated_values_feed_later_lags(tmp_path: Path) -> None:
    models = {(VAR, h): PlusOne() for h in (1, 2, 3)} | {(NDVI, 3): None}
    store = run(models, "2026-12", tmp_path)
    base = 10.0  # T001 at the cutoff (offset 0)
    for month, expected in ((202609, base + 1), (202610, base + 1), (202611, base + 1),
                            (202612, base + 2)):  # H3 from 202609, itself projected
        assert store.read(period(month)).loc["T001", VAR] == pytest.approx(expected)
    methods = store.months_index()["202612"]["metodos"]
    assert methods == {VAR: "lightgbm_h3", NDVI: "persistencia_h3"}


def test_missing_horizon_falls_back_to_same_month_last_year(tmp_path: Path) -> None:
    models = {(VAR, 1): None, (NDVI, 3): None}
    store = run(models, "2026-10", tmp_path)
    index = store.months_index()
    assert index["202609"]["metodos"][NDVI] == "sazonal_t-12"
    assert index["202610"]["metodos"][NDVI] == "sazonal_t-12"
    # 202609 - 12 = 202509, offset 11 from the cutoff -> 0.1 * 11
    assert store.read(period(202609)).loc["T001", NDVI] == pytest.approx(1.1)


def test_year_turn_uses_destination_month(tmp_path: Path) -> None:
    frame = history("2025-12")
    store = run({(VAR, 1): MonthCosine(), (NDVI, 1): None}, "2026-01", tmp_path, frame,
                cutoff="2025-12")
    assert store.read(period(202601)).loc["T001", VAR] == pytest.approx(np.cos(2 * np.pi / 12))


def test_missing_lag_and_gap_month_stay_null(tmp_path: Path) -> None:
    frame = history()
    gap = (frame["location_id"] == "T002") & (frame["anomes"] == 202602)
    frame = frame[~gap]  # T002 has no February: must stay absent, not shift lags
    window = window_for(frame)
    assert np.isnan(window[period(202602)].loc["T002", VAR])
    ids = window[period(202608)].index
    values, methods, nulls = project_month(window, period(202701), bundle(
        {(VAR, 3): PlusOne(), (NDVI, 3): None}), ids, [VAR, NDVI])
    # 202701 with H3 -> origin 202610 (not in this window) -> null for everybody
    assert nulls[VAR] == 2
    values, _, nulls = project_month(window, period(202701), bundle(
        {(VAR, 1): PlusOne(), (NDVI, 3): None}, cutoff="2026-12"), ids, [VAR, NDVI])
    assert nulls[VAR] == 2  # origin 202612 lags missing in a window ending in 202608
    february = window_for(frame, "2026-02")  # window 202412..202602, T002 lacks 202602
    values, _, nulls = project_month(february, period(202603), bundle(
        {(VAR, 1): PlusOne(), (NDVI, 3): None}, cutoff="2026-02"), ids, [VAR, NDVI])
    assert np.isnan(values.loc["T002", VAR]) and not np.isnan(values.loc["T001", VAR])
    assert nulls[VAR] == 1


def test_batches_match_full_run(tmp_path: Path) -> None:
    models = {(VAR, h): PlusOne() for h in (1, 2, 3)} | {(NDVI, 3): None}
    whole = run(models, "2027-03", tmp_path / "a", batch_size=50_000)
    split = run(models, "2027-03", tmp_path / "b", batch_size=1)
    for month in pd.period_range("2026-09", "2027-03", freq="M"):
        pd.testing.assert_frame_equal(whole.read(month), split.read(month))


def test_checkpoint_resume_equals_from_scratch(tmp_path: Path) -> None:
    models = {(VAR, h): PlusOne() for h in (1, 2, 3)} | {(NDVI, 3): None}
    scratch = run(models, "2027-06", tmp_path / "scratch")
    partial = run(models, "2026-12", tmp_path / "resume")
    resumed = run(models, "2027-06", tmp_path / "resume")
    assert partial.last_contiguous(period(202608)) == period(202706)
    for month in pd.period_range("2026-09", "2027-06", freq="M"):
        pd.testing.assert_frame_equal(scratch.read(month), resumed.read(month))


def test_running_job_can_extend_destination(tmp_path: Path) -> None:
    models = {(VAR, 1): None, (NDVI, 3): None}
    seen: list[int] = []
    store = TrajectoryStore(tmp_path, "t")
    last = project_until(period(202610), bundle(models), store, lambda: window_for(history()),
                         [VAR, NDVI], should_extend=lambda: period(202612),
                         progress=lambda m, done, total, _: seen.append(total))
    assert last == period(202612)
    assert seen[-1] == 4


def test_store_ignores_month_without_index_entry(tmp_path: Path) -> None:
    models = {(VAR, 1): None, (NDVI, 3): None}
    store = run(models, "2026-10", tmp_path)
    (store.folder / "202612.parquet").write_bytes(b"lixo")  # orphan file after a crash
    assert store.last_contiguous(period(202608)) == period(202610)


def test_load_bundle_contract(tmp_path: Path) -> None:
    good = tmp_path / "ok.pkl"
    good.write_bytes(pickle.dumps({"origem": "2026-08", "modelos": {(VAR, 1): None}}))
    loaded = load_bundle(good)
    assert loaded.cutoff == period(202608) and loaded.horizons(VAR) == [1]
    assert len(loaded.sha256) == 64
    bad = tmp_path / "bad.pkl"
    bad.write_bytes(pickle.dumps({"modelos": {}}))
    with pytest.raises(ValueError):
        load_bundle(bad)
    wrong_key = tmp_path / "wrong.pkl"
    wrong_key.write_bytes(pickle.dumps({"origem": "2026-08", "modelos": {VAR: None}}))
    with pytest.raises(ValueError):
        load_bundle(wrong_key)


def test_origin_labels_and_seasonal_base() -> None:
    cutoff = period(202608)
    assert origin_for(period(202608), cutoff, 3, "recursiva", set()) == "observada"
    assert origin_for(period(202611), cutoff, 3, "recursiva", set()) == "prevista"
    assert origin_for(period(204007), cutoff, 3, "recursiva", set()) == "extrapolada"
    assert origin_for(period(204007), cutoff, 3, "auto", set()) == "cenario_sazonal"
    assert origin_for(period(202609), cutoff, 3, "sazonal", set()) == "cenario_sazonal"
    assert seasonal_base(period(204007), cutoff) == period(202607)
    assert seasonal_base(period(204012), cutoff) == period(202512)
