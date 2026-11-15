"""Regional aggregation engine.

All raster statistics are AREA-WEIGHTED with the exact spherical area of each pixel
(R = 1737.4 km).  L1 membership is computed per pixel; L0 statistics are computed
from the same pixels grouped by parent (L1 regions nest exactly in L0).
coverage_fraction = (spherical area of valid pixels in region) / (region area).
For row-sampled rasters each sampled line carries the weight of `row_stride` lines,
so coverage remains an unbiased area estimate.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from lunar_common import PROCESSED, R_MOON_KM, assign_points, load_regions

OBS_DIR = PROCESSED / "obs"
OBS_DIR.mkdir(parents=True, exist_ok=True)
STATUS = PROCESSED / "dataset_status.json"

_REGS = None


def regions():
    global _REGS
    if _REGS is None:
        _REGS = load_regions()
    return _REGS


def l1_table():
    r = regions()
    return r[r.level == 1].reset_index(drop=True)


def l0_table():
    r = regions()
    return r[r.level == 0].reset_index(drop=True)


def l1_index(lat, lon):
    return assign_points(
        np.asarray(lat, dtype=np.float64), np.asarray(lon, dtype=np.float64), l1_table()
    )


def set_status(dataset_id, status, note=""):
    from lunar_common import update_json

    order = ["catalogued", "downloaded", "decoded", "processed", "regionalized", "validated"]

    def fn(s):
        prev = s.get(dataset_id, {}).get("status")
        if prev in order and status in order and order.index(prev) > order.index(status):
            return
        s[dataset_id] = dict(status=status, note=note)

    update_json(STATUS, fn)


def read_status():
    if not STATUS.exists():
        return {}
    t = STATUS.read_text(encoding="utf-8")
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return json.JSONDecoder().raw_decode(t)[0]


# ---------------------------------------------------------------------------
def cyl_grid_from_label(lines, samples, res, maxlat, westlon):
    lat = maxlat - (np.arange(lines) + 0.5) / res
    lon = np.mod(westlon + (np.arange(samples) + 0.5) / res, 360.0)
    return lat, lon


def cyl_pixel_area(lat_c, res):
    """km^2 for each latitude row of a cylindrical grid with res px/deg."""
    d = 0.5 / res
    lat1 = np.radians(np.clip(lat_c - d, -90, 90))
    lat2 = np.radians(np.clip(lat_c + d, -90, 90))
    return R_MOON_KM**2 * np.radians(1.0 / res) * np.abs(np.sin(lat2) - np.sin(lat1))


def polar_stereo_latlon(lines, samples, scale_m, line_off, samp_off, south, R=1737400.0, rows=None):
    """Lat/lon (deg) and true pixel area (km^2) for spherical polar stereographic grids
    (LOLA convention: x = (s - S0)*scale, y = (L0 - l)*scale; 0-based pixel centres)."""
    li = np.arange(lines) if rows is None else np.asarray(rows)
    x = (np.arange(samples)[None, :] - samp_off) * scale_m
    y = (line_off - li[:, None]) * scale_m
    rho = np.hypot(x, y)
    c = 2.0 * np.arctan(rho / (2.0 * R))
    lat = (-1 if south else 1) * (90.0 - np.degrees(c))
    lon = np.degrees(np.arctan2(x, y)) if south else np.degrees(np.arctan2(x, -y))
    lon = np.mod(lon, 360.0)
    k = 2.0 / (1.0 + np.sin(np.radians(np.abs(lat))))  # scale factor
    area = (scale_m / 1000.0) ** 2 / k**2
    return lat, lon, area


# ---------------------------------------------------------------------------
def _wquant(v, w, qs):
    o = np.argsort(v, kind="stable")
    v, w = v[o], w[o]
    cw = np.cumsum(w) - 0.5 * w
    cw /= w.sum()
    return np.interp(np.asarray(qs) / 100.0, cw, v)


def aggregate(
    values,
    weights,
    idx,
    stats=("mean", "std", "min", "max", "p05", "p25", "p50", "p75", "p95"),
    extra=None,
    valid=None,
):
    """values, weights, idx: 1-D arrays (same length). idx = L1 row index (-1 = none).
    extra: dict name -> function(v, w) -> float, evaluated per region on valid pixels.
    Returns DataFrame indexed by region_id with stats + area_valid_km2 + n."""
    values = np.asarray(values, dtype=np.float64).ravel()
    weights = np.asarray(weights, dtype=np.float64).ravel()
    idx = np.asarray(idx).ravel()
    ok = np.isfinite(values) & (idx >= 0) & np.isfinite(weights) & (weights > 0)
    if valid is not None:
        ok &= np.asarray(valid).ravel()
    l1 = l1_table()
    parent_of = l1.parent_region_id.values
    l0 = l0_table()
    l0_pos = {rid: i for i, rid in enumerate(l0.region_id)}
    idx_l0 = np.full(idx.shape, -1, dtype=np.int32)
    m = idx >= 0
    idx_l0[m] = np.array([l0_pos[p] for p in parent_of])[idx[m]]
    rows = []
    for _level, ids, table in ((1, idx, l1), (0, idx_l0, l0)):
        sel = ok & (ids >= 0)
        if sel.sum() == 0:
            for rid in table.region_id:
                rows.append(dict(region_id=rid, n=0, area_valid_km2=0.0))
            continue
        v, w, g = values[sel], weights[sel], ids[sel]
        order = np.argsort(g, kind="stable")
        v, w, g = v[order], w[order], g[order]
        bounds = np.searchsorted(g, np.arange(len(table) + 1))
        for k, rid in enumerate(table.region_id):
            a, b = bounds[k], bounds[k + 1]
            row = dict(region_id=rid, n=int(b - a), area_valid_km2=float(w[a:b].sum()))
            if b > a:
                vv, ww = v[a:b], w[a:b]
                mean = float(np.sum(vv * ww) / np.sum(ww))
                if "mean" in stats:
                    row["mean"] = mean
                if "std" in stats:
                    row["std"] = float(np.sqrt(np.sum(ww * (vv - mean) ** 2) / np.sum(ww)))
                if "min" in stats:
                    row["min"] = float(vv.min())
                if "max" in stats:
                    row["max"] = float(vv.max())
                ps = [s for s in stats if s.startswith("p") and s[1:].isdigit()]
                if ps:
                    qv = _wquant(vv, ww, [int(s[1:]) for s in ps])
                    for s, q in zip(ps, qv, strict=True):
                        row[s] = float(q)
                if extra:
                    for name, fn in extra.items():
                        row[name] = float(fn(vv, ww))
            rows.append(row)
    df = pd.DataFrame(rows).set_index("region_id")
    area = regions().set_index("region_id").area_km2
    df["coverage_fraction"] = (df["area_valid_km2"] / area.loc[df.index]).clip(upper=1.0)
    return df


def frac_above(th):
    return lambda v, w: np.sum(w[v > th]) / np.sum(w)


def frac_below(th):
    return lambda v, w: np.sum(w[v < th]) / np.sum(w)


# ---------------------------------------------------------------------------
def records_from_agg(df, var_map, meta, unit_map=None):
    """Convert an aggregate DataFrame to long observation records.

    var_map: {column_in_df: variable_name}; meta: provenance dict shared by all.
    Regions with zero valid pixels get NO value record (coverage is recorded separately)."""
    recs = []
    for rid, row in df.iterrows():
        cov = float(row.get("coverage_fraction", np.nan))
        for col, var in var_map.items():
            if col not in row or not np.isfinite(row[col]):
                continue
            r = dict(meta)
            r.update(
                region_id=rid,
                variable=var,
                value=float(row[col]),
                unit=(unit_map or {}).get(var, meta.get("unit", "")),
                coverage_fraction=cov,
                n_samples=int(row.get("n", 0)),
            )
            recs.append(r)
    return recs


def coverage_records(df, variables, meta):
    out = []
    for rid, row in df.iterrows():
        for var in variables:
            out.append(
                dict(
                    region_id=rid,
                    variable=var,
                    dataset=meta["dataset"],
                    coverage_fraction=float(row.get("coverage_fraction", 0.0) or 0.0),
                    n_samples=int(row.get("n", 0)),
                    resolution=meta.get("resolution", ""),
                    quality=meta.get("quality", ""),
                    uncertainty=meta.get("uncertainty", ""),
                )
            )
    return out


def save_obs(dataset_id, recs, cov=None):
    df = pd.DataFrame(recs)
    df.to_parquet(OBS_DIR / f"obs_{dataset_id}.parquet", index=False)
    if cov is not None:
        pd.DataFrame(cov).to_parquet(OBS_DIR / f"cov_{dataset_id}.parquet", index=False)
    return df
