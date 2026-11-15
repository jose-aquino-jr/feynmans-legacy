"""Illumination / Earth visibility / sky-view: official LOLA polar products + this
project's global horizon model (compute_illumination.py)."""

from __future__ import annotations

import numpy as np
from lunar_common import PROCESSED
from proc_common import meta, proj_num, read_pds_img
from regionalize import (
    aggregate,
    coverage_records,
    cyl_pixel_area,
    frac_above,
    frac_below,
    l1_index,
    polar_stereo_latlon,
    records_from_agg,
    save_obs,
    set_status,
)

STRIDE = 2  # every 2nd line and sample of the 240 m products (480 m sampling)


def _polar(dataset_id, img):
    rows = np.arange(0, 6420, STRIDE)
    a, m, _ = read_pds_img(dataset_id, img, rows=rows)
    a = a[:, ::STRIDE]
    south = proj_num(m, "CENTER_LATITUDE") < 0
    lat, lon, area = polar_stereo_latlon(
        m["lines"],
        m["samples"],
        proj_num(m, "MAP_SCALE"),
        proj_num(m, "LINE_PROJECTION_OFFSET"),
        proj_num(m, "SAMPLE_PROJECTION_OFFSET"),
        south,
        rows=rows,
    )
    lat, lon, area = lat[:, ::STRIDE], lon[:, ::STRIDE], area[:, ::STRIDE] * STRIDE * STRIDE
    lim = proj_num(m, "MAXIMUM_LATITUDE") if south else proj_num(m, "MINIMUM_LATITUDE")
    inside = (lat <= lim) if south else (lat >= lim)
    a = np.where(inside, a, np.nan)
    return a, lat, lon, area


def _both(dataset_id, name_fmt):
    out = []
    for p in ("n", "s"):
        out.append(_polar(dataset_id, name_fmt.format(p)))
    a = np.concatenate([o[0].ravel() for o in out])
    lat = np.concatenate([o[1].ravel() for o in out])
    lon = np.concatenate([o[2].ravel() for o in out])
    area = np.concatenate([o[3].ravel() for o in out])
    return a, lat, lon, area


def check_convention():
    """Shackleton crater floor (89.66S, 129.2E) must be PSR; return value found."""
    a, lat, lon, area = _polar("LOLA_LPSR_65", "lpsr_65s_240m_201608.img")
    # nearest sample to Shackleton centre
    tgt_lat, tgt_lon = -89.66, 129.2
    p = np.radians
    x = np.cos(p(lat)) * np.cos(p(lon))
    y = np.cos(p(lat)) * np.sin(p(lon))
    z = np.sin(p(lat))
    tx = np.cos(p(tgt_lat)) * np.cos(p(tgt_lon))
    ty = np.cos(p(tgt_lat)) * np.sin(p(tgt_lon))
    tz = np.sin(p(tgt_lat))
    k = np.nanargmax(x * tx + y * ty + z * tz)
    return float(a.ravel()[k]), float(lat.ravel()[k]), float(lon.ravel()[k])


def process_official():
    recs, cov = [], []
    # --- average solar visibility
    a, lat, lon, area = _both("LOLA_AVGVISIB_65", "avgvisib_65{}_240m_201608.img")
    set_status("LOLA_AVGVISIB_65", "decoded")
    idx = l1_index(lat, lon)
    b = meta(
        "LOLA_AVGVISIB_65",
        unit="fraction",
        resolution="240 m/px, sampled every 2nd line/sample (480 m)",
        quality="official model (Mazarico et al. 2011, 2016 release)",
        processing_method="area-weighted stats of time-averaged visible fraction of the solar disc",
    )
    ag = aggregate(
        a,
        area,
        idx,
        stats=("mean", "p05", "p50", "p95", "max"),
        extra={
            "g50": frac_above(0.5),
            "g70": frac_above(0.7),
            "g80": frac_above(0.8),
            "z": frac_below(0.001),
        },
    )
    vm = {
        "mean": "illum_avg_visibility_lola",
        "p05": "illum_avg_visibility_lola_p05",
        "p50": "illum_avg_visibility_lola_p50",
        "p95": "illum_avg_visibility_lola_p95",
        "max": "illum_avg_visibility_lola_max",
    }
    recs += records_from_agg(ag, vm, b)
    fm = {
        "g50": "illum_lola_area_frac_gt50pct",
        "g70": "illum_lola_area_frac_gt70pct",
        "g80": "illum_lola_area_frac_gt80pct",
        "z": "illum_lola_area_frac_lt0p1pct",
    }
    recs += records_from_agg(
        ag,
        fm,
        dict(
            b,
            processing_method="area fraction of pixels whose average solar visibility exceeds/below threshold",
        ),
    )
    cov += coverage_records(ag, list(vm.values()) + list(fm.values()), b)
    set_status("LOLA_AVGVISIB_65", "regionalized")
    # --- PSR
    a, lat, lon, area = _both("LOLA_LPSR_65", "lpsr_65{}_240m_201608.img")
    set_status("LOLA_LPSR_65", "decoded")
    psr = np.where(np.isfinite(a), (a > 0.5).astype(float), np.nan)
    idx = l1_index(lat, lon)
    b = meta(
        "LOLA_LPSR_65",
        unit="fraction",
        resolution="240 m/px sampled at 480 m",
        quality="official; PSRs smaller than ~0.5 km unresolved (lower bound)",
        processing_method="area fraction of LOLA permanently-shadowed pixels",
    )
    ag = aggregate(psr, area, idx, stats=("mean",), extra={"km2": lambda v, w: np.sum(w * v)})
    recs += records_from_agg(ag, {"mean": "psr_area_fraction_lola"}, b)
    recs += records_from_agg(
        ag,
        {"km2": "psr_area_km2_lola"},
        dict(b, unit="km2", processing_method="sum of PSR pixel areas"),
    )
    cov += coverage_records(ag, ["psr_area_fraction_lola", "psr_area_km2_lola"], b)
    set_status("LOLA_LPSR_65", "regionalized")
    # --- Earth visibility
    a, lat, lon, area = _both("LOLA_AVGVISIB_EARTH_65", "avgvisib_65{}_240m_201608_earth.img")
    set_status("LOLA_AVGVISIB_EARTH_65", "decoded")
    idx = l1_index(lat, lon)
    b = meta(
        "LOLA_AVGVISIB_EARTH_65",
        unit="fraction",
        resolution="240 m/px sampled at 480 m",
        quality="official model",
        processing_method="area-weighted stats of time-averaged visible fraction of the Earth disc",
    )
    ag = aggregate(
        a,
        area,
        idx,
        stats=("mean", "p50", "p95"),
        extra={"g50": frac_above(0.5), "z": frac_below(0.001)},
    )
    vm = {
        "mean": "earth_visibility_lola",
        "p50": "earth_visibility_lola_p50",
        "p95": "earth_visibility_lola_p95",
    }
    fm = {"g50": "earth_vis_lola_area_frac_gt50pct", "z": "earth_vis_lola_area_frac_never"}
    recs += records_from_agg(ag, vm, b)
    recs += records_from_agg(
        ag, fm, dict(b, processing_method="area fraction above/below visibility threshold")
    )
    cov += coverage_records(ag, list(vm.values()) + list(fm.values()), b)
    set_status("LOLA_AVGVISIB_EARTH_65", "regionalized")
    save_obs("LOLA_POLAR_ILLUMINATION", recs, cov)
    return len(recs)


def process_model():
    z = np.load(PROCESSED / "illumination_model_4ppd.npz")
    lat, lon = z["lat"], z["lon"]
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    area = np.repeat(cyl_pixel_area(lat, 4)[:, None], len(lon), axis=1)
    set_status("DERIVED_HORIZON_ILLUM", "processed")
    base = meta(
        "DERIVED_HORIZON_ILLUM",
        resolution="4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km)",
        quality="model: sub-4 km topography (small craters/PSRs) not resolved",
        uncertainty="validated against LOLA AVGVISIB at |lat|>65 (see validation report)",
    )
    recs, cov = [], []

    def add(
        arr,
        var,
        unit,
        how,
        stats=("mean", "min", "max", "p05", "p50", "p95"),
        extra=None,
        extra_names=None,
    ):
        nonlocal recs, cov
        b = dict(base, unit=unit, processing_method=how)
        ag = aggregate(arr, area, idx, stats=stats, extra=extra)
        vm = {s: (var if s == "mean" else f"{var}_{s}") for s in stats}
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
        if extra:
            recs += records_from_agg(ag, extra_names, dict(b, unit="fraction"))
            cov += coverage_records(ag, list(extra_names.values()), b)

    add(
        z["sun_vis"],
        "illumination_fraction",
        "fraction",
        "time-mean visible fraction of solar disc over one eclipse year (2 h steps), horizon from LOLA DEM",
        extra={"g50": frac_above(0.5), "g70": frac_above(0.7)},
        extra_names={
            "g50": "illumination_model_area_frac_gt50pct",
            "g70": "illumination_model_area_frac_gt70pct",
        },
    )
    add(
        z["insol_h"],
        "insolation_horizontal_mean",
        "W/m2",
        "time-mean S0*f*sin(e) on a horizontal surface, S0=1361 W/m2",
    )
    add(
        z["insol_track"],
        "solar_irradiance_tracking_mean",
        "W/m2",
        "time-mean S0*f on a sun-tracking panel (energy potential upper bound, no shadowing by panel height)",
    )
    dm = np.where(np.isfinite(z["dark_max_h"]), z["dark_max_h"], np.nan)
    add(
        dm / 24.0,
        "longest_darkness_days",
        "day",
        "longest continuous period with <1% of solar disc visible within one eclipse year (cells never lit excluded)",
        stats=("mean", "min", "max", "p50"),
    )
    never = (z["ever_lit"] < 0.5).astype(float)
    add(
        never,
        "never_lit_area_fraction_model",
        "fraction",
        "area fraction of 7.6 km cells with zero solar disc visibility all year (coarse PSR proxy; lower bound)",
        stats=("mean",),
    )
    add(
        z["sun_gt50"],
        "sun_gt50pct_time_fraction",
        "fraction",
        "fraction of time with more than half of the solar disc visible",
        stats=("mean", "min", "max"),
    )
    add(
        z["earth_vis"],
        "earth_visibility_fraction",
        "fraction",
        "time-mean visible fraction of Earth disc (optical libration model), horizon from LOLA DEM",
        extra={"never": frac_below(1e-4), "always": frac_above(0.999)},
        extra_names={
            "never": "earth_never_visible_area_frac",
            "always": "earth_always_visible_area_frac",
        },
    )
    add(
        z["svf"],
        "sky_view_factor",
        "fraction",
        "mean over 36 azimuths of cos^2(horizon elevation) for a horizontal surface (radiative sky view)",
        stats=("mean", "min", "p05"),
    )
    add(
        z["sky_solid_frac"],
        "open_sky_solid_angle_fraction",
        "fraction",
        "fraction of upper-hemisphere solid angle unobstructed by terrain = relative exposure to isotropic "
        "GCR/SPE flux vs flat open ground (geometric shielding proxy)",
        stats=("mean", "min", "p05"),
    )
    add(
        z["horizon_mean"],
        "horizon_elevation_mean",
        "degree",
        "mean horizon elevation over 36 azimuths",
        stats=("mean", "max", "p95"),
    )
    save_obs("DERIVED_HORIZON_ILLUM", recs, cov)
    set_status("DERIVED_HORIZON_ILLUM", "regionalized")
    return len(recs)


if __name__ == "__main__":
    import sys

    if "check" in sys.argv:
        print("Shackleton PSR value, lat, lon:", check_convention())
    if "official" in sys.argv:
        print("official", process_official())
    if "model" in sys.argv:
        print("model", process_model())
