"""Diviner processors.

GCP (Williams et al. 2017): fixed-width ASCII, 113-byte records ordered
longitude-major -> latitude -> local time (0.25 h).  Each longitude column
(20 lat x 96 LT = 1920 records) is contiguous; we read every 2nd longitude column
(1.0 deg longitude spacing, all latitudes, all local times) by HTTP Range.

PRP (Paige et al. 2010): 2,880,000 triangles per pole on a 1200 x 1200 square mesh
(2 triangles per square, ~0.5 km) centred on the pole to 80 deg.  We read every 8th
mesh row (2400 contiguous records) and weight every triangle by its exact 3-D area.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import io
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from dataset_registry import by_id
from lunar_common import PROCESSED
from lunar_io import get_range, head, save_manifest_entry
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

REC = 113
BLOCK = 20 * 96
LON_STRIDE = 2


def _fetch_blocks(url, block_bytes, header, block_ids, nconn=8):
    size, lastmod, final = head(url)

    def job(k):
        return k, get_range(final, header + k * block_bytes, block_bytes)

    with ThreadPoolExecutor(nconn) as ex:
        res = dict(ex.map(job, block_ids))
    h = hashlib.sha256()
    for k in sorted(res):
        h.update(res[k])
    return res, dict(
        url=url,
        size_bytes=size,
        remote_last_modified=lastmod,
        sha256_of_fetched_blocks=h.hexdigest(),
        n_blocks=len(res),
        block_bytes=block_bytes,
    )


def gcp_band(url):
    blocks, info = _fetch_blocks(url, BLOCK * REC, REC, list(range(0, 720, LON_STRIDE)))
    txt = b"".join(blocks[k] for k in sorted(blocks))
    df = pd.read_csv(
        io.BytesIO(txt),
        header=None,
        skipinitialspace=True,
        names=["clon", "clat", "ltim", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "tbol"],
        usecols=["clon", "clat", "ltim", "tbol"],
    )
    return df, info


def derive_gcp_bins(df):
    """Per (lon, lat) bin derived diurnal metrics from 96 local-time Tbol values."""
    df = df.sort_values(["clon", "clat", "ltim"])
    nb = len(df) // 96
    T = df["tbol"].to_numpy().reshape(nb, 96).astype(np.float64)
    T[T <= -9000] = np.nan
    T[T <= 0] = np.nan  # non-physical brightness temperature -> invalid
    lt = df["ltim"].to_numpy()[:96]
    lon = df["clon"].to_numpy()[::96]
    lat = df["clat"].to_numpy()[::96]
    nval = np.isfinite(T).sum(1)
    day = (lt >= 10) & (lt <= 14)
    night = (lt >= 19) | (lt <= 5.5)
    with np.errstate(all="ignore"):
        has_noon = np.isfinite(T[:, day]).any(1)
        has_night = np.isfinite(T[:, night]).sum(1) >= 8
        tmax = np.where(has_noon, np.nanmax(T, 1), np.nan)
        tmin = np.where(has_night, np.nanmin(np.where(night[None, :], T, np.nan), 1), np.nan)
        noon = np.nanmean(T[:, (lt >= 11.5) & (lt <= 12.5)], 1)
        midnight = np.nanmean(T[:, (lt >= 23.5) | (lt <= 0.5)], 1)
        predawn = np.nanmean(T[:, (lt >= 5.0) & (lt <= 5.75)], 1)
        # diurnal mean: periodic linear interpolation if >= 50 % of bins valid and max gap <= 2 h
        tmean = np.full(nb, np.nan)
        for i in np.where(nval >= 48)[0]:
            ok = np.isfinite(T[i])
            x = lt[ok]
            gaps = np.diff(np.r_[x, x[0] + 24])
            if gaps.max() <= 2.0 + 1e-6:
                tmean[i] = np.mean(np.interp(lt, x, T[i, ok], period=24))
    return pd.DataFrame(
        dict(
            lon=np.mod(lon, 360),
            lat=lat,
            n_lt=nval,
            tmax=tmax,
            tmin=tmin,
            tmean=tmean,
            tnoon=noon,
            tmidnight=midnight,
            tpredawn=predawn,
            amp=tmax - tmin,
        )
    )


def process_gcp():
    ds = by_id()["DIVINER_GCP_TBOL"]
    out = PROCESSED / "diviner_gcp_bins.parquet"
    parts = []
    if out.exists():
        allb = pd.read_parquet(out)
    else:
        cache_dir = PROCESSED / "diviner_gcp_parts"
        cache_dir.mkdir(exist_ok=True)
        for u in ds["urls"]:
            t0 = time.time()
            part = cache_dir / (u.rsplit("/", 1)[-1] + ".parquet")
            if part.exists():
                parts.append(pd.read_parquet(part))
                continue
            df, info = gcp_band(u)
            b = derive_gcp_bins(df)
            b.to_parquet(part, index=False)
            parts.append(b)
            save_manifest_entry(
                f"DIVINER_GCP_TBOL:{u.rsplit('/', 1)[-1]}",
                dict(
                    dataset_id="DIVINER_GCP_TBOL",
                    mode="remote_block_sample",
                    lon_stride=LON_STRIDE,
                    note="every 2nd 0.5-deg longitude column; all latitudes and local times",
                    retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
                    **info,
                ),
            )
            print(f"  {u.rsplit('/', 1)[-1]}: {len(b)} bins, {time.time() - t0:.0f}s", flush=True)
        allb = pd.concat(parts, ignore_index=True)
        allb.to_parquet(out, index=False)
    set_status("DIVINER_GCP_TBOL", "processed")
    lat, lon = allb.lat.to_numpy(), allb.lon.to_numpy()
    w = cyl_pixel_area(lat, 2.0) * LON_STRIDE  # 0.5 deg bins, each sampled column stands for 2
    idx = l1_index(lat, lon)
    base = meta(
        "DIVINER_GCP_TBOL",
        quality="Tbol = bolometric BRIGHTNESS temperature (not kinetic); empty LT bins excluded",
        resolution="0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg)",
        unit="K",
        processing_method="",
    )
    recs, cov = [], []
    specs = {
        "tmax": ("tbol_max", "max over local time of Tbol (requires >=1 valid bin 10-14 h)"),
        "tmin": ("tbol_min_night", "min over night local times 19-5.5 h (>=8 valid night bins)"),
        "tmean": (
            "tbol_diurnal_mean",
            "mean over 24 h after periodic linear interpolation (>=50% bins, gaps<=2 h)",
        ),
        "tnoon": ("tbol_noon", "mean Tbol 11.5-12.5 h local time"),
        "tmidnight": ("tbol_midnight", "mean Tbol 23.5-0.5 h local time"),
        "tpredawn": ("tbol_predawn", "mean Tbol 5.0-5.75 h local time (coldest pre-dawn)"),
        "amp": ("tbol_diurnal_amplitude", "per-bin Tbol max minus night min"),
    }
    for col, (var, how) in specs.items():
        b = dict(
            base,
            processing_method=f"per 0.5-deg bin: {how}; then area-weighted regional statistics",
        )
        ag = aggregate(
            allb[col].to_numpy(), w, idx, stats=("mean", "std", "min", "max", "p05", "p50", "p95")
        )
        vm = {
            s: f"{var}_{s}" if s != "mean" else var
            for s in ("mean", "std", "min", "max", "p05", "p50", "p95")
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    save_obs("DIVINER_GCP_TBOL", recs, cov)
    set_status("DIVINER_GCP_TBOL", "regionalized")
    return len(recs)


PRP_REC = 210
MESH = 1200
PRP_STRIDE = 8


def process_prp():
    ds = by_id()["DIVINER_PRP"]
    out = PROCESSED / "diviner_prp_sample.parquet"
    if out.exists():
        allp = pd.read_parquet(out)
    else:
        parts = []
        for u in ds["urls"][:2]:
            rows = list(range(0, MESH, PRP_STRIDE))
            blocks, info = _fetch_blocks(u, 2 * MESH * PRP_REC, PRP_REC, rows)
            txt = b"".join(blocks[k] for k in sorted(blocks))
            df = pd.read_csv(
                io.BytesIO(txt),
                header=None,
                skipinitialspace=True,
                names=[
                    "x1",
                    "y1",
                    "z1",
                    "x2",
                    "y2",
                    "z2",
                    "x3",
                    "y3",
                    "z3",
                    "clon",
                    "clat",
                    "calt",
                    "temp_avg",
                    "temp_max",
                    "ice_depth",
                ],
            )
            p1 = df[["x1", "y1", "z1"]].to_numpy()
            p2 = df[["x2", "y2", "z2"]].to_numpy()
            p3 = df[["x3", "y3", "z3"]].to_numpy()
            df["area_km2"] = 0.5 * np.linalg.norm(np.cross(p2 - p1, p3 - p1), axis=1) * PRP_STRIDE
            df["pole"] = "north" if "north" in u else "south"
            parts.append(
                df[
                    [
                        "clon",
                        "clat",
                        "calt",
                        "temp_avg",
                        "temp_max",
                        "ice_depth",
                        "area_km2",
                        "pole",
                    ]
                ]
            )
            save_manifest_entry(
                f"DIVINER_PRP:{u.rsplit('/', 1)[-1]}",
                dict(
                    dataset_id="DIVINER_PRP",
                    mode="remote_block_sample",
                    mesh_row_stride=PRP_STRIDE,
                    retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
                    **info,
                ),
            )
            print(f"  {u.rsplit('/', 1)[-1]}: {len(df)} triangles", flush=True)
        allp = pd.concat(parts, ignore_index=True)
        allp.to_parquet(out, index=False)
    set_status("DIVINER_PRP", "processed")
    lat, lon = allp.clat.to_numpy(), np.mod(allp.clon.to_numpy(), 360)
    idx = l1_index(lat, lon)
    w = allp.area_km2.to_numpy()
    base = meta(
        "DIVINER_PRP",
        resolution="~0.5 km triangles; every 8th mesh row sampled",
        quality="model-derived (thermal model fit to first-year Diviner data)",
    )
    recs, cov = [], []
    for col, var, how in (
        ("temp_avg", "annual_mean_surface_temperature", "annual average surface temperature"),
        ("temp_max", "annual_max_surface_temperature", "annual maximum surface temperature"),
    ):
        v = allp[col].to_numpy().astype(float)
        v[v <= 0] = np.nan
        b = dict(
            base,
            unit="K",
            processing_method=f"area-weighted stats of PRP {how} (modelled kinetic temperature)",
        )
        ex = {"cold110": frac_below(110.0)} if col == "temp_max" else None
        ag = aggregate(v, w, idx, stats=("mean", "min", "max", "p05", "p50", "p95"), extra=ex)
        vm = {
            s: (var if s == "mean" else f"{var}_{s}")
            for s in ("mean", "min", "max", "p05", "p50", "p95")
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
        if ex:
            bb = dict(
                b,
                unit="fraction",
                processing_method="area fraction with annual max T < 110 K "
                "(water-ice surface cold-trap threshold, Paige et al. 2010; Hayne et al. 2015)",
            )
            recs += records_from_agg(ag, {"cold110": "coldtrap_area_fraction_tmax_lt110K"}, bb)
            cov += coverage_records(ag, ["coldtrap_area_fraction_tmax_lt110K"], bb)
    d = allp.ice_depth.to_numpy().astype(float)
    valid_t = allp.temp_avg.to_numpy() > 0
    stable = np.where(valid_t, (d >= 0).astype(float), np.nan)
    b = dict(
        base,
        unit="fraction",
        quality="model; ice_depth=-999 interpreted as 'no stable ice in modelled column'",
        processing_method="area fraction of triangles with a modelled ice-stability depth (>=0 m)",
    )
    ag = aggregate(stable, w, idx, stats=("mean",))
    recs += records_from_agg(ag, {"mean": "ice_stable_area_fraction"}, b)
    cov += coverage_records(ag, ["ice_stable_area_fraction"], b)
    surf = np.where(valid_t, ((d >= 0) & (d <= 0.01)).astype(float), np.nan)
    ag = aggregate(surf, w, idx, stats=("mean",))
    b2 = dict(
        b,
        processing_method="area fraction where modelled ice-stability depth <= 1 cm (surface-stable)",
    )
    recs += records_from_agg(ag, {"mean": "ice_surface_stable_area_fraction"}, b2)
    cov += coverage_records(ag, ["ice_surface_stable_area_fraction"], b2)
    dd = np.where(d >= 0, d, np.nan)
    ag = aggregate(dd, w, idx, stats=("mean", "p50"))
    b3 = dict(
        base, unit="m", processing_method="area-weighted ice-stability depth where ice is stable"
    )
    recs += records_from_agg(
        ag, {"mean": "ice_stability_depth_mean", "p50": "ice_stability_depth_p50"}, b3
    )
    cov += coverage_records(ag, ["ice_stability_depth_mean", "ice_stability_depth_p50"], b3)
    save_obs("DIVINER_PRP", recs, cov)
    set_status("DIVINER_PRP", "regionalized")
    return len(recs)


def _l3(
    dataset_id,
    img,
    var,
    unit,
    how,
    stats=("mean", "std", "p05", "p50", "p95"),
    extra=None,
    extra_names=None,
    valid_range=None,
):
    a, m, _ = read_pds_img(dataset_id, img)
    set_status(dataset_id, "decoded")
    qnote = ""
    if valid_range is not None:
        bad = np.isfinite(a) & ((a < valid_range[0]) | (a > valid_range[1]))
        nb, nv = int(bad.sum()), int(np.isfinite(a).sum())
        a[bad] = np.nan
        qnote = f"; {nb} of {nv} pixels outside physical range {valid_range} set invalid (non-physical model output)"
    res = proj_num(m, "MAP_RESOLUTION")
    lat, lon = cyl_grid_from_label(
        m["lines"],
        m["samples"],
        res,
        proj_num(m, "MAXIMUM_LATITUDE"),
        proj_num(m, "WESTERNMOST_LONGITUDE"),
    )
    # memory: process in latitude slabs
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    area = np.repeat(cyl_pixel_area(lat, res)[:, None], len(lon), axis=1)
    base = meta(
        dataset_id, unit=unit, processing_method=how, quality="Diviner GDR L3 (+/-60 deg)" + qnote
    )
    ag = aggregate(a, area, idx, stats=stats, extra=extra)
    vm = {s: (var if s == "mean" else f"{var}_{s}") for s in stats}
    recs = records_from_agg(ag, vm, base)
    cov = coverage_records(ag, list(vm.values()), base)
    if extra:
        recs += records_from_agg(ag, extra_names, dict(base, unit="fraction"))
        cov += coverage_records(ag, list(extra_names.values()), base)
    save_obs(dataset_id, recs, cov)
    set_status(dataset_id, "regionalized")
    return len(recs)


def process_ra():
    return _l3(
        "DIVINER_RA",
        "dgdr_ra_avg_cyl_032_img.img",
        "rock_abundance",
        "fraction",
        "area-weighted stats of Diviner rock abundance (Bandfield et al. 2011)",
        stats=("mean", "std", "p50", "p95", "max"),
        extra={"r1": frac_above(0.01), "r5": frac_above(0.05)},
        extra_names={
            "r1": "rock_abundance_area_frac_gt1pct",
            "r5": "rock_abundance_area_frac_gt5pct",
        },
        valid_range=(0.0, 1.0),
    )


def process_st():
    return _l3(
        "DIVINER_ST",
        "dgdr_st_avg_cyl_032_img.img",
        "regolith_temp_anomaly_night",
        "K",
        "area-weighted stats of rock-free regolith night temperature deviation from global mean "
        "(Bandfield et al. 2011); proxy of fine-regolith thermophysical properties",
    )


def process_cf():
    return _l3(
        "DIVINER_CF",
        "dgdr_nen_cf_clc_cyl_032_img.img",
        "christiansen_feature",
        "micrometre",
        "area-weighted stats of normalized equatorial-noon Christiansen feature position",
    )


if __name__ == "__main__":
    import sys

    fns = dict(gcp=process_gcp, prp=process_prp, ra=process_ra, st=process_st, cf=process_cf)
    for k in sys.argv[1:] or fns:
        print(k, fns[k]())
