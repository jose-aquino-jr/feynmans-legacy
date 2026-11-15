"""Shared constants and helpers for the lunar base pipeline.

Coordinate reference (applies to every derived product of this project):
  * Body: Moon (IAU code 301). Reference frame: Moon Mean-Earth/Polar-Axis (ME),
    the frame used by LOLA/LRO PDS products (DE421-based ME realisation).
  * Latitude: planetocentric, degrees, -90..+90.
  * Longitude: positive EAST, 0..360 degrees.
  * Reference surface: sphere of radius 1737.4 km (IAU/IAG lunar mean radius,
    also the LOLA reference sphere). OGC/IAU CRS: IAU_2015:30100.
  * NO terrestrial EPSG code is ever applied to lunar data.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if os.environ.get("LUNAR_DATA_ROOT"):
    ROOT = Path(os.environ["LUNAR_DATA_ROOT"]).resolve()
    _DATA = ROOT
elif (
    _HERE.name == "lua" and _HERE.parent.name == "scripts"
):  # feynmans-legacy repo: scripts/lua -> data/lua
    ROOT = _HERE.parents[1] / "data" / "lua"
    _DATA = ROOT
else:  # standalone layout: <root>/scripts, <root>/data/{raw,processed}, <root>/outputs, <root>/reports
    ROOT = _HERE.parent
    _DATA = ROOT / "data"
RAW = _DATA / "raw"
PROCESSED = _DATA / "processed"
OUTPUTS = ROOT / "outputs"
REPORTS = ROOT / "reports"
for _d in (RAW, PROCESSED, OUTPUTS, REPORTS):
    _d.mkdir(parents=True, exist_ok=True)

R_MOON_KM = 1737.4
MOON_AREA_KM2 = 4.0 * math.pi * R_MOON_KM**2
CRS_NAME = "IAU_2015:30100"
CRS_DESCRIPTION = (
    "Moon 2000 geographic, planetocentric latitude, east-positive "
    "longitude 0-360, sphere R=1737.4 km, Mean-Earth/Polar-Axis frame"
)

# ---------------------------------------------------------------------------
# Region scheme (equal-area latitude/longitude graticule, see build_lunar_regions)
# ---------------------------------------------------------------------------
# L0: two polar caps + two hemispheric belts of 5 sectors (72 deg).  Each = 1/12 sphere.
LAT_CAP_L0 = math.degrees(math.asin(5.0 / 6.0))  # 56.4427 deg
# L1 polar cap: inner cap of 1/48 sphere + 3 ring sectors of 120 deg
LAT_CAP_L1 = math.degrees(math.asin(23.0 / 24.0))  # 73.3985 deg
# L1 belt split: equal-area mid latitude between 0 and LAT_CAP_L0
LAT_MID_L1 = math.degrees(math.asin(5.0 / 12.0))  # 24.6243 deg


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_regions():
    import pandas as pd

    return pd.read_csv(OUTPUTS / "lunar_regions.csv")


def region_index_grid(lat_centers: np.ndarray, lon_centers: np.ndarray, level: int):
    """Return integer array (len(lat), len(lon)) of region row indices for a lat/lon grid.

    lat_centers, lon_centers: 1-D arrays of pixel-centre coordinates (deg, lon 0..360).
    Index refers to the row order of lunar_regions.csv filtered to `level`.
    """
    regs = load_regions()
    regs = regs[regs.level == level].reset_index(drop=True)
    lat2 = lat_centers[:, None] * np.ones_like(lon_centers)[None, :]
    lon2 = np.mod(lon_centers[None, :], 360.0) * np.ones_like(lat_centers)[:, None]
    return assign_points(lat2, lon2, regs)


def assign_points(lat: np.ndarray, lon: np.ndarray, regs) -> np.ndarray:
    """Vectorised assignment of points to regions given lat/lon bounds.

    Bounds are half-open [lat_min, lat_max) x [lon_min, lon_max), except that
    lat_max == 90 is closed and lon_max == 360 wraps.  Returns -1 if unassigned.
    """
    lon = np.mod(lon, 360.0)
    out = np.full(lat.shape, -1, dtype=np.int32)
    for i, r in enumerate(regs.itertuples()):
        in_lat = (lat >= r.lat_min) & ((lat < r.lat_max) | ((r.lat_max >= 90.0) & (lat <= 90.0)))
        in_lon = (lon >= r.lon_min) & (lon < r.lon_max)
        out[in_lat & in_lon & (out < 0)] = i
    return out


def pixel_area_km2(lat_centers: np.ndarray, dlat_deg: float, dlon_deg: float) -> np.ndarray:
    """Exact spherical area of equirectangular pixels (km^2), per latitude row."""
    lat1 = np.radians(np.clip(lat_centers - dlat_deg / 2, -90, 90))
    lat2 = np.radians(np.clip(lat_centers + dlat_deg / 2, -90, 90))
    return R_MOON_KM**2 * np.radians(dlon_deg) * np.abs(np.sin(lat2) - np.sin(lat1))


class FileLock:
    """Cross-process lock (exclusive lock file) for read-modify-write of shared JSON files."""

    def __init__(self, path: Path, timeout=120):
        self.lock = Path(str(path) + ".lock")
        self.timeout = timeout

    def __enter__(self):
        import time

        t0 = time.time()
        while True:
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() - t0 > self.timeout:  # stale lock
                    try:
                        os.remove(self.lock)
                    except OSError:
                        pass
                time.sleep(0.05)

    def __exit__(self, *a):
        try:
            os.remove(self.lock)
        except OSError:
            pass


def update_json(path: Path, fn):
    """Locked, atomic read-modify-write of a JSON dict: fn(dict) mutates it."""
    path = Path(path)
    with FileLock(path):
        d = {}
        if path.exists():
            t = path.read_text(encoding="utf-8")
            try:
                d = json.loads(t)
            except json.JSONDecodeError:
                d = json.JSONDecoder().raw_decode(t)[0]  # recover first complete object
        fn(d)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp, path)
        return d


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def weighted_stats(values: np.ndarray, weights: np.ndarray, percentiles=(5, 25, 50, 75, 95)):
    """Area-weighted stats ignoring NaN. Returns dict (empty values -> NaN)."""
    m = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    out = {"n": int(m.sum())}
    if m.sum() == 0:
        out.update(mean=np.nan, std=np.nan, min=np.nan, max=np.nan)
        for p in percentiles:
            out[f"p{p:02d}"] = np.nan
        return out
    v = values[m].astype(np.float64)
    w = weights[m].astype(np.float64)
    mean = np.sum(v * w) / np.sum(w)
    var = np.sum(w * (v - mean) ** 2) / np.sum(w)
    order = np.argsort(v)
    v_s, w_s = v[order], w[order]
    cw = np.cumsum(w_s) - 0.5 * w_s
    cw /= np.sum(w_s)
    out.update(mean=float(mean), std=float(np.sqrt(var)), min=float(v.min()), max=float(v.max()))
    for p in percentiles:
        out[f"p{p:02d}"] = float(np.interp(p / 100.0, cw, v_s))
    return out
