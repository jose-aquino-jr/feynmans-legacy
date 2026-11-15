"""Gravity (GRAIL GRGM1200A), crustal thickness (Wieczorek et al. 2013, 4 models),
crustal magnetic field (Ravat et al. 2020) and in-situ point observations."""

from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd
from lunar_common import PROCESSED, RAW
from proc_common import meta, proj_num, read_pds_img
from regionalize import (
    aggregate,
    coverage_records,
    cyl_grid_from_label,
    cyl_pixel_area,
    frac_above,
    l1_index,
    l1_table,
    records_from_agg,
    save_obs,
    set_status,
)


def _cyl(dataset_id, img):
    a, m, _ = read_pds_img(dataset_id, img)
    res = proj_num(m, "MAP_RESOLUTION")
    lat, lon = cyl_grid_from_label(
        m["lines"],
        m["samples"],
        res,
        proj_num(m, "MAXIMUM_LATITUDE"),
        proj_num(m, "WESTERNMOST_LONGITUDE"),
    )
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    return a, l1_index(LAT, LON), np.repeat(cyl_pixel_area(lat, res)[:, None], len(lon), axis=1)


def process_grail():
    recs, cov = [], []
    for dsid, img, var, how in (
        (
            "GRAIL_GRGM1200A_FA",
            "gggrx_1200a_anom_l660.img",
            "gravity_freeair",
            "free-air gravity anomaly (GRGM1200A to degree 660, reference radius 1738 km)",
        ),
        (
            "GRAIL_GRGM1200A_BOUG",
            "gggrx_1200a_boug_l660.img",
            "gravity_bouguer",
            "Bouguer gravity anomaly (GRGM1200A, degree 660; crustal density per PDS label)",
        ),
        (
            "GRAIL_GRGM1200A_ERR",
            "gggrx_1200a_anomerr_l660.img",
            "gravity_freeair_sigma",
            "1-sigma error of free-air anomaly (propagated from GRGM1200A covariance)",
        ),
    ):
        a, idx, area = _cyl(dsid, img)
        set_status(dsid, "decoded")
        b = meta(
            dsid,
            unit="mGal",
            processing_method=f"area-weighted stats of {how}",
            quality="global, uniform; 1 mGal = 1e-5 m s-2. Anomaly, NOT total gravity; independent of altitude",
        )
        stats = ("mean",) if var.endswith("sigma") else ("mean", "std", "min", "max", "p05", "p95")
        extra = {"pos200": frac_above(200.0)} if var == "gravity_bouguer" else None
        ag = aggregate(a, area, idx, stats=stats, extra=extra)
        vm = {s: (var if s == "mean" else f"{var}_{s}") for s in stats}
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
        if extra:
            recs += records_from_agg(
                ag,
                {"pos200": "gravity_bouguer_area_frac_gt200mgal"},
                dict(
                    b,
                    unit="fraction",
                    processing_method="area fraction with Bouguer anomaly > +200 mGal "
                    "(descriptive threshold for strong positive mass anomalies, e.g. mascon centres)",
                ),
            )
            cov += coverage_records(ag, ["gravity_bouguer_area_frac_gt200mgal"], b)
        set_status(dsid, "regionalized")
    save_obs("GRAIL_GRAVITY", recs, cov)
    return len(recs)


def _read_crust_grid(path):
    """Model*_thick.dat: whitespace table. Detect layout: (lon lat value) triples or a lat x lon matrix."""
    a = np.loadtxt(path)
    if a.ndim == 1 and a.size == 721 * 1441:
        # Archive doc: ASCII raster, first value (90N, 0E), last (90S, 360E), 0.25 deg spacing, 721 x 1441.
        g = a.reshape(721, 1441)[:, :1440]  # drop duplicated 360E column
        lat = 90 - np.arange(721) * 0.25
        lon = np.arange(1440) * 0.25
        LAT, LON = np.meshgrid(lat, lon, indexing="ij")
        return (
            LAT.ravel(),
            LON.ravel(),
            g.ravel(),
            "0.25-deg node grid 721x1441 (principal-axis frame, ~0.02 deg from ME)",
        )
    if a.ndim == 2 and a.shape[1] == 3:
        lon, lat, v = a[:, 0], a[:, 1], a[:, 2]
        if np.nanmax(np.abs(lat)) > 90:  # columns swapped
            lon, lat = lat, lon
        return lat, np.mod(lon, 360), v, "xyz"
    nlat, nlon = a.shape
    lat = 90 - np.arange(nlat) * 180.0 / (nlat - 1)
    lon = np.arange(nlon) * 360.0 / nlon
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    return (
        LAT.ravel(),
        LON.ravel(),
        a.ravel(),
        f"matrix {nlat}x{nlon} (assumed 90..-90 inclusive, 0..360 exclusive)",
    )


def process_crust():
    dsid = "GRAIL_CRUST_WIECZOREK2013"
    d = RAW / dsid
    grids, layout = [], ""
    for k in range(1, 5):
        f = d / f"Model{k}_thick.dat"
        if not f.exists():
            continue
        lat, lon, v, layout = _read_crust_grid(f)
        grids.append(v)
    if not grids:
        return 0
    set_status(dsid, "decoded")
    V = np.vstack(grids)
    mean = V.mean(0)
    spread = V.max(0) - V.min(0)
    # equal-angle grid: weight by cos(lat) (relative spherical area)
    w = np.cos(np.radians(lat)).clip(1e-6)
    idx = l1_index(lat, lon)
    b = meta(
        dsid,
        unit="km",
        resolution=f"grid layout: {layout}",
        quality="model; mean of the 4 published models (Wieczorek et al. 2013)",
        uncertainty="model spread (max-min of 4 models) reported separately",
        processing_method="cos(lat)-weighted regional stats of mean crustal thickness of Models 1-4",
    )
    ag = aggregate(mean, w, idx, stats=("mean", "std", "min", "max", "p05", "p95"))
    vm = {
        s: ("crust_thickness" if s == "mean" else f"crust_thickness_{s}")
        for s in ("mean", "std", "min", "max", "p05", "p95")
    }
    recs = records_from_agg(ag, vm, b)
    cov = coverage_records(ag, list(vm.values()), b)
    ag2 = aggregate(spread, w, idx, stats=("mean",))
    b2 = dict(
        b, processing_method="regional mean of per-cell spread (max-min) among the 4 crustal models"
    )
    recs += records_from_agg(ag2, {"mean": "crust_thickness_model_spread"}, b2)
    cov += coverage_records(ag2, ["crust_thickness_model_spread"], b2)
    # coverage of a point grid is not an area: set to 1 where values exist
    for r in recs:
        r["coverage_fraction"] = 1.0
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


def process_magnetic():
    dsid = "RAVAT2020_MAG"
    f = RAW / dsid / "ravat2020_lunar_magnetic_model_viewcontent.bin"
    head = f.read_bytes()[:4]
    if head[:2] == b"PK":
        z = zipfile.ZipFile(f)
        name = [n for n in z.namelist() if n.lower().endswith(".dat")][0]
        txt = z.open(name)
        (PROCESSED / "ravat_zip_listing.txt").write_text("\n".join(z.namelist()))
    else:
        txt = open(f, "rb")
        name = f.name
    df = pd.read_csv(txt, sep=r"\s+", header=None, comment="#", engine="c", on_bad_lines="skip")
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    df = df.iloc[:, :6]
    df.columns = ["lon", "lat", "br", "bt", "bp", "btot"]
    set_status(dsid, "decoded")
    lat, lon = df.lat.to_numpy(), np.mod(df.lon.to_numpy(), 360)
    w = np.cos(np.radians(lat)).clip(1e-6)
    idx = l1_index(lat, lon)
    b = meta(
        dsid,
        unit="nT",
        product=name,
        quality="model at the lunar surface (L1-norm inversion)",
        processing_method="cos(lat)-weighted regional stats of total crustal field |B| at the surface",
    )
    ag = aggregate(
        df.btot.to_numpy(),
        w,
        idx,
        stats=("mean", "p50", "p95", "max"),
        extra={"g10": frac_above(10.0), "g50": frac_above(50.0)},
    )
    vm = {
        "mean": "magnetic_field_surface_mean",
        "p50": "magnetic_field_surface_p50",
        "p95": "magnetic_field_surface_p95",
        "max": "magnetic_field_surface_max",
    }
    recs = records_from_agg(ag, vm, b)
    recs += records_from_agg(
        ag,
        {"g10": "magnetic_area_frac_gt10nT", "g50": "magnetic_area_frac_gt50nT"},
        dict(
            b,
            unit="fraction",
            processing_method="area fraction with |B| above threshold (descriptive)",
        ),
    )
    for r in recs:
        r["coverage_fraction"] = 1.0
    cov = coverage_records(
        ag, list(vm.values()) + ["magnetic_area_frac_gt10nT", "magnetic_area_frac_gt50nT"], b
    )
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


def process_lp_mag():
    dsid = "LP_MAG_L4"
    parts = []
    for a in range(0, 360, 60):
        f = RAW / dsid / f"b_{a}-{a + 60}e_tot.tab"
        t = pd.read_csv(
            f, sep=r"\s+", header=None, names=["lat", "lon", "btot", "n"], engine="python"
        )
        parts.append(t.apply(pd.to_numeric, errors="coerce"))
    df = pd.concat(parts, ignore_index=True).dropna()
    set_status(dsid, "decoded")
    nz = int((df.n <= 0).sum())
    v = np.where(df.n > 0, df.btot, np.nan)  # bins with no samples carry no observation
    lat, lon = df.lat.to_numpy(), np.mod(df.lon.to_numpy(), 360)
    w = np.cos(np.radians(lat)).clip(1e-6)
    idx = l1_index(lat, lon)
    b = meta(
        dsid,
        unit="nT",
        quality=f"observed field at 37 km; only bins with >=1 sample used; {nz} bins with n=0 (empty or interpolated: ambiguous) excluded; +/-60 deg",
        processing_method="cos(lat)-weighted regional stats of LP MAG total crustal field |B| at 37 km",
    )
    ag = aggregate(
        v,
        w,
        idx,
        stats=("mean", "p50", "p95", "max"),
        extra={"g2": frac_above(2.0), "g10": frac_above(10.0)},
    )
    vm = {
        "mean": "magnetic_field_37km_mean",
        "p50": "magnetic_field_37km_p50",
        "p95": "magnetic_field_37km_p95",
        "max": "magnetic_field_37km_max",
    }
    recs = records_from_agg(ag, vm, b)
    fm = {"g2": "magnetic_37km_area_frac_gt2nT", "g10": "magnetic_37km_area_frac_gt10nT"}
    recs += records_from_agg(
        ag,
        fm,
        dict(
            b,
            unit="fraction",
            processing_method="area fraction of bins with |B| above threshold (descriptive)",
        ),
    )
    cov = coverage_records(ag, list(vm.values()) + list(fm.values()), b)
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


# ----------------------------------------------------------------------------- in-situ point observations
POINTS = [
    # Published in-situ measurements (point observations, NOT regional values).
    dict(
        variable="heat_flow_insitu",
        value=21.0,
        unit="mW/m2",
        lat=26.13,
        lon=3.63,
        mission="Apollo 15",
        instrument="Heat Flow Experiment (HFE)",
        observation_date="1971-1974",
        uncertainty="+/-3 mW/m2 (published)",
        source="Langseth, Keihm & Peters 1976, Proc. Lunar Sci. Conf. 7, 3143",
        quality="pre-1980 in-situ; only direct measurement",
    ),
    dict(
        variable="heat_flow_insitu",
        value=14.0,
        unit="mW/m2",
        lat=20.19,
        lon=30.77,
        mission="Apollo 17",
        instrument="Heat Flow Experiment (HFE)",
        observation_date="1972-1977",
        uncertainty="+/-2.5 mW/m2; some compilations cite 16 mW/m2; later reanalyses (Nagihara et al. 2018) question long-term drift",
        source="Langseth, Keihm & Peters 1976, Proc. Lunar Sci. Conf. 7, 3143",
        quality="pre-1980 in-situ; only direct measurement",
    ),
    dict(
        variable="radiation_dose_equivalent_surface_insitu",
        value=1369.0,
        unit="uSv/day",
        lat=-45.44,
        lon=177.60,
        mission="Chang'e-4",
        instrument="Lunar Lander Neutrons and Dosimetry (LND)",
        observation_date="2019-01/2019-02",
        uncertainty="+/-35 uSv/day (published)",
        source="Zhang et al. 2020, Science Advances 6, eaaz1334",
        quality="single-site surface measurement during solar minimum; GCR dominated",
    ),
]


def process_points():
    l1 = l1_table()
    par = dict(zip(l1.region_id, l1.parent_region_id, strict=True))
    groups = {}
    for p in POINTS:
        k = l1_index(np.array([p["lat"]]), np.array([p["lon"]]))[0]
        rid = l1.region_id.iloc[k]
        for region in (rid, par[rid]):
            groups.setdefault((region, p["variable"]), []).append(p)
    recs = []
    for (region, var), ps in groups.items():
        j = lambda key, ps=ps: " | ".join(dict.fromkeys(str(q[key]) for q in ps))  # noqa: E731
        recs.append(
            dict(
                region_id=region,
                variable=var,
                value=float(np.mean([q["value"] for q in ps])),
                unit=ps[0]["unit"],
                dataset="INSITU_POINTS",
                mission=j("mission"),
                instrument=j("instrument"),
                product="published in-situ measurement",
                version="as published",
                resolution="point observation(s) at "
                + "; ".join(f"{q['lat']:.2f}, {q['lon']:.2f}E" for q in ps),
                observation_date=j("observation_date"),
                time_period="point_observation",
                quality=j("quality"),
                uncertainty=j("uncertainty"),
                coverage_fraction=0.0,
                n_samples=len(ps),
                processing_method=(
                    "mean of the site values inside the region"
                    if len(ps) > 1
                    else "site value assigned to the region containing it"
                )
                + "; NOT representative of the whole region",
                source=j("source"),
            )
        )
    save_obs("INSITU_POINTS", recs)
    return len(recs)


if __name__ == "__main__":
    import sys

    fns = dict(
        grail=process_grail, crust=process_crust, lpmag=process_lp_mag, points=process_points
    )
    for k in sys.argv[1:] or fns:
        print(k, fns[k]())
