"""LOLA topography processors: LDEM_16, LDSM_16, LDRM_16, LDEC_4."""

from __future__ import annotations

import numpy as np
from lunar_common import PROCESSED, R_MOON_KM
from proc_common import meta, proj_num, read_pds_img
from regionalize import (
    aggregate,
    coverage_records,
    cyl_grid_from_label,
    cyl_pixel_area,
    frac_above,
    frac_below,
    l1_index,
    records_from_agg,
    save_obs,
    set_status,
)
from scipy import ndimage


def _grid(m):
    res = proj_num(m, "MAP_RESOLUTION")
    lat, lon = cyl_grid_from_label(
        m["lines"],
        m["samples"],
        res,
        proj_num(m, "MAXIMUM_LATITUDE"),
        proj_num(m, "WESTERNMOST_LONGITUDE"),
    )
    return res, lat, lon


def _idx_area(lat, lon, res):
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    area = np.repeat(cyl_pixel_area(lat, res)[:, None], len(lon), axis=1)
    return idx, area


def process_ldem16():
    z, m, _ = read_pds_img("LOLA_LDEM_16", "ldem_16.img")
    z = (
        z - 1737400.0
    )  # height above the 1737.4 km reference sphere (label: radius = DN*0.5 + 1737400)
    res, lat, lon = _grid(m)
    idx, area = _idx_area(lat, lon, res)
    np.save(PROCESSED / "ldem16_height_m.npy", z.astype(np.float32))
    set_status("LOLA_LDEM_16", "decoded")

    # --- derivatives on the sphere (centred differences, periodic in longitude)
    dphi = np.radians(1 / res)
    dy = R_MOON_KM * 1000 * dphi
    dx = (R_MOON_KM * 1000 * np.cos(np.radians(lat)) * dphi)[:, None]
    zx = (np.roll(z, -1, 1) - np.roll(z, 1, 1)) / (2 * dx)
    zy = np.empty_like(z)
    zy[1:-1] = (z[:-2] - z[2:]) / (2 * dy)  # north-positive
    zy[0] = zy[1]
    zy[-1] = zy[-2]
    slope = np.degrees(np.arctan(np.hypot(zx, zy)))
    # pixels within 1 deg of the poles: dx -> 0, derivative unreliable -> NoData
    polar_bad = np.abs(lat) > 89.0
    slope[polar_bad, :] = np.nan
    aspect = np.degrees(np.arctan2(-zx, -zy)) % 360  # downslope direction, clockwise from north
    lap = (np.roll(z, -1, 1) - 2 * z + np.roll(z, 1, 1)) / dx**2
    lap[1:-1] += (z[:-2] - 2 * z[1:-1] + z[2:]) / dy**2
    lap[[0, -1], :] = np.nan
    lap[polar_bad, :] = np.nan
    lap_km = lap * 1e3  # 1/km
    # topographic position index: height minus mean in an 11x11 window (~21 km at the equator)
    tpi = z - ndimage.uniform_filter(z, size=11, mode="wrap")
    tpi[polar_bad, :] = np.nan
    set_status("LOLA_LDEM_16", "processed")

    base = meta(
        "LOLA_LDEM_16",
        quality="good: LOLA altimetry; interpolated where no tracks (see LDEC)",
        processing_method="area-weighted regional statistics of LDEM_16 heights above R=1737.4 km sphere",
    )
    recs, cov = [], []
    ag = aggregate(
        z,
        area,
        idx,
        extra={
            "hyps": lambda v, w: (
                (np.sum(v * w) / np.sum(w) - v.min()) / max(v.max() - v.min(), 1e-9)
            )
        },
    )
    ag["relief_p05_p95"] = ag["p95"] - ag["p05"]
    ag["range_minmax"] = ag["max"] - ag["min"]
    vm = {
        "mean": "elevation_mean",
        "std": "elevation_std",
        "min": "elevation_min",
        "max": "elevation_max",
        "p05": "elevation_p05",
        "p25": "elevation_p25",
        "p50": "elevation_p50",
        "p75": "elevation_p75",
        "p95": "elevation_p95",
        "relief_p05_p95": "relief_range",
        "range_minmax": "elevation_range_minmax",
    }
    recs += records_from_agg(ag, vm, dict(base, unit="m"))
    recs += records_from_agg(
        ag,
        {"hyps": "hypsometric_integral"},
        dict(
            base, unit="dimensionless", processing_method="(mean-min)/(max-min) of LDEM_16 heights"
        ),
    )
    cov += coverage_records(ag, list(vm.values()) + ["hypsometric_integral"], base)

    b2 = dict(
        base,
        resolution="1.9 km pixel; centred-difference baseline ~3.8 km",
        processing_method="slope from centred differences of LDEM_16 on the sphere (|lat|>89 excluded)",
    )
    ag = aggregate(
        slope,
        area,
        idx,
        stats=("mean", "std", "p50", "p90", "p95", "max"),
        extra={"f5": frac_above(5), "f10": frac_above(10), "f20": frac_above(20)},
    )
    vm = {
        "mean": "slope_km_mean",
        "std": "slope_km_std",
        "p50": "slope_km_p50",
        "p90": "slope_km_p90",
        "p95": "slope_km_p95",
        "max": "slope_km_max",
    }
    recs += records_from_agg(ag, vm, dict(b2, unit="degree"))
    recs += records_from_agg(
        ag,
        {"f5": "slope_km_frac_gt5", "f10": "slope_km_frac_gt10", "f20": "slope_km_frac_gt20"},
        dict(b2, unit="fraction"),
    )
    cov += coverage_records(
        ag,
        list(vm.values()) + ["slope_km_frac_gt5", "slope_km_frac_gt10", "slope_km_frac_gt20"],
        b2,
    )

    # aspect: circular statistics of downslope direction for pixels with slope > 2 deg
    ok = slope > 2
    ang = np.radians(aspect)
    agc = aggregate(np.cos(ang), area, idx, stats=("mean",), valid=ok)
    ags = aggregate(np.sin(ang), area, idx, stats=("mean",), valid=ok)
    agc["dir"] = np.degrees(np.arctan2(ags["mean"], agc["mean"])) % 360
    agc["R"] = np.hypot(agc["mean"], ags["mean"])
    b3 = dict(
        base,
        processing_method="circular mean of downslope azimuth (clockwise from N) for pixels with slope>2 deg; "
        "R = mean resultant length (0 = no preferred aspect)",
    )
    recs += records_from_agg(agc, {"dir": "aspect_circular_mean"}, dict(b3, unit="degree"))
    recs += records_from_agg(agc, {"R": "aspect_resultant_length"}, dict(b3, unit="dimensionless"))
    cov += coverage_records(agc, ["aspect_circular_mean", "aspect_resultant_length"], b3)

    b4 = dict(
        base,
        processing_method="Laplacian of LDEM_16 heights (positive = concave/valley, negative = convex/ridge)",
    )
    ag = aggregate(
        lap_km,
        area,
        idx,
        stats=("mean", "std", "p05", "p95"),
        extra={"concave": frac_above(0.0), "convex": frac_below(0.0)},
    )
    recs += records_from_agg(
        ag,
        {
            "mean": "curvature_laplacian_mean",
            "std": "curvature_laplacian_std",
            "p05": "curvature_laplacian_p05",
            "p95": "curvature_laplacian_p95",
        },
        dict(b4, unit="1/km"),
    )
    recs += records_from_agg(
        ag,
        {"concave": "concave_area_fraction", "convex": "convex_area_fraction"},
        dict(b4, unit="fraction"),
    )
    cov += coverage_records(
        ag,
        [
            "curvature_laplacian_mean",
            "curvature_laplacian_std",
            "curvature_laplacian_p05",
            "curvature_laplacian_p95",
            "concave_area_fraction",
            "convex_area_fraction",
        ],
        b4,
    )

    b5 = dict(
        base,
        processing_method="TPI = height minus 11x11-pixel (~21 km) moving mean; std and depression fraction",
    )
    ag = aggregate(
        tpi,
        area,
        idx,
        stats=("std", "p05", "p95"),
        extra={"dep": frac_below(-100.0), "hill": frac_above(100.0)},
    )
    recs += records_from_agg(
        ag,
        {"std": "tpi_21km_std", "p05": "tpi_21km_p05", "p95": "tpi_21km_p95"},
        dict(b5, unit="m"),
    )
    recs += records_from_agg(
        ag,
        {"dep": "tpi_depression_fraction", "hill": "tpi_high_fraction"},
        dict(b5, unit="fraction"),
    )
    cov += coverage_records(
        ag,
        [
            "tpi_21km_std",
            "tpi_21km_p05",
            "tpi_21km_p95",
            "tpi_depression_fraction",
            "tpi_high_fraction",
        ],
        b5,
    )

    save_obs("LOLA_LDEM_16", recs, cov)
    np.save(PROCESSED / "ldem16_slope_deg.npy", slope.astype(np.float32))
    set_status("LOLA_LDEM_16", "regionalized")
    return len(recs)


def process_ldsm16():
    s, m, _ = read_pds_img("LOLA_LDSM_16", "ldsm_16.img")
    res, lat, lon = _grid(m)
    idx, area = _idx_area(lat, lon, res)
    set_status("LOLA_LDSM_16", "decoded")
    base = meta(
        "LOLA_LDSM_16",
        quality="good; track-based, interpolated between tracks",
        processing_method="area-weighted stats of LOLA 240 m-baseline bidirectional slope (LDSM_16)",
    )
    ex = {f"f{t}": frac_above(t) for t in (5, 10, 15, 20, 25, 30)}
    ex.update({"lt5": frac_below(5), "lt10": frac_below(10)})
    ag = aggregate(s, area, idx, stats=("mean", "std", "p50", "p90", "p95", "max"), extra=ex)
    vm = {
        "mean": "slope_240m_mean",
        "std": "slope_240m_std",
        "p50": "slope_240m_p50",
        "p90": "slope_240m_p90",
        "p95": "slope_240m_p95",
        "max": "slope_240m_max",
    }
    recs = records_from_agg(ag, vm, dict(base, unit="degree"))
    fm = {f"f{t}": f"slope_240m_frac_gt{t}" for t in (5, 10, 15, 20, 25, 30)}
    fm.update({"lt5": "slope_240m_frac_lt5", "lt10": "slope_240m_frac_lt10"})
    recs += records_from_agg(ag, fm, dict(base, unit="fraction"))
    cov = coverage_records(ag, list(vm.values()) + list(fm.values()), base)
    save_obs("LOLA_LDSM_16", recs, cov)
    np.save(PROCESSED / "ldsm16_slope240_deg.npy", s.astype(np.float32))
    set_status("LOLA_LDSM_16", "regionalized")
    return len(recs)


def process_ldrm16():
    r, m, _ = read_pds_img("LOLA_LDRM_16", "ldrm_16.img")
    res, lat, lon = _grid(m)
    idx, area = _idx_area(lat, lon, res)
    r[r < 0] = np.nan  # negative RMS is physically impossible -> treated as invalid (counted in QA)
    set_status("LOLA_LDRM_16", "decoded")
    base = meta(
        "LOLA_LDRM_16",
        quality="track-based roughness, interpolated between tracks",
        processing_method="area-weighted stats of LOLA RMS residual heights (LDRM_16)",
    )
    ag = aggregate(r, area, idx, stats=("mean", "std", "p50", "p90", "p95"))
    vm = {
        "mean": "roughness_rms_mean",
        "std": "roughness_rms_std",
        "p50": "roughness_rms_p50",
        "p90": "roughness_rms_p90",
        "p95": "roughness_rms_p95",
    }
    recs = records_from_agg(ag, vm, dict(base, unit="m"))
    save_obs("LOLA_LDRM_16", recs, coverage_records(ag, list(vm.values()), base))
    set_status("LOLA_LDRM_16", "regionalized")
    return len(recs)


def process_ldec4():
    c, m, _ = read_pds_img("LOLA_LDEC_4", "ldec_4.img")
    res, lat, lon = _grid(m)
    idx, area = _idx_area(lat, lon, res)
    base = meta(
        "LOLA_LDEC_4",
        quality="count layer",
        processing_method="area-weighted LOLA shot counts per 4 px/deg cell",
    )
    ag = aggregate(
        c,
        area,
        idx,
        stats=("mean", "p05", "p50"),
        extra={"zero": lambda v, w: np.sum(w[v <= 0]) / np.sum(w)},
    )
    vm = {
        "mean": "lola_shots_per_cell_mean",
        "p05": "lola_shots_per_cell_p05",
        "p50": "lola_shots_per_cell_p50",
    }
    recs = records_from_agg(ag, vm, dict(base, unit="count per 7.6 km cell"))
    recs += records_from_agg(ag, {"zero": "lola_empty_cell_fraction"}, dict(base, unit="fraction"))
    save_obs(
        "LOLA_LDEC_4",
        recs,
        coverage_records(ag, list(vm.values()) + ["lola_empty_cell_fraction"], base),
    )
    set_status("LOLA_LDEC_4", "regionalized")
    return len(recs)


if __name__ == "__main__":
    for f in (process_ldem16, process_ldsm16, process_ldrm16, process_ldec4):
        print(f.__name__, f())
