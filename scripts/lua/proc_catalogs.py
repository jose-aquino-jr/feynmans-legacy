"""Vector catalogs: craters (Robbins 2018), LROC shapefiles (Copernican craters, new
craters, lobate scarps, wrinkle ridges, swirls, IMPs, global mare, Hiesinger mare
ages), pits, and the USGS Unified Geologic Map.

Polygon area fractions are computed by rasterising polygons on a 0.1 deg
planetocentric grid (point-in-polygon of cell centres; ~3 km) and summing exact
spherical cell areas per region.  Polylines are measured on the sphere (great-circle
segment lengths) and assigned to regions by segment midpoint.  Point features are
assigned by their coordinates.
"""

from __future__ import annotations

import math
import re
import zipfile

import numpy as np
import pandas as pd
import shapefile  # pyshp
import shapely
from lunar_common import PROCESSED, R_MOON_KM, RAW
from proc_common import meta
from regionalize import (
    aggregate,
    coverage_records,
    cyl_pixel_area,
    l1_index,
    l1_table,
    records_from_agg,
    regions,
    save_obs,
    set_status,
)
from scipy.spatial import cKDTree

GRID_RES = 10  # px/deg for polygon rasterisation
_LATG = 90 - (np.arange(180 * GRID_RES) + 0.5) / GRID_RES
_LONG = (np.arange(360 * GRID_RES) + 0.5) / GRID_RES
_AREA_ROW = cyl_pixel_area(_LATG, GRID_RES)
_IDX = None


def grid_idx():
    global _IDX
    if _IDX is None:
        LAT, LON = np.meshgrid(_LATG, _LONG, indexing="ij")
        _IDX = l1_index(LAT, LON)
    return _IDX


def region_area_series():
    return regions().set_index("region_id").area_km2


def l1_to_both(values_by_l1: pd.Series, how="sum"):
    """Expand an L1-indexed Series to L1 + L0 (sum or area-weighted mean)."""
    l1 = l1_table()
    s = values_by_l1.reindex(l1.region_id).fillna(0.0)
    if how == "sum":
        l0 = s.groupby(l1.set_index("region_id").parent_region_id).sum()
    else:
        a = l1.set_index("region_id").area_km2
        l0 = (s * a).groupby(l1.set_index("region_id").parent_region_id).sum() / a.groupby(
            l1.set_index("region_id").parent_region_id
        ).sum()
    return pd.concat([s, l0])


def rasterize(geoms, values=None):
    """Return dict value -> boolean mask (or single mask) of 0.1-deg cells inside geoms (lon 0-360)."""
    mask = np.zeros((len(_LATG), len(_LONG)), dtype=np.int32) - 1
    for k, g in enumerate(geoms):
        if g is None or g.is_empty:
            continue
        minx, miny, maxx, maxy = g.bounds
        i0 = max(0, int((90 - maxy) * GRID_RES) - 1)
        i1 = min(len(_LATG), int((90 - miny) * GRID_RES) + 2)
        j0 = max(0, int(minx * GRID_RES) - 1)
        j1 = min(len(_LONG), int(maxx * GRID_RES) + 2)
        if i1 <= i0 or j1 <= j0:
            continue
        X, Y = np.meshgrid(_LONG[j0:j1], _LATG[i0:i1])
        inside = shapely.contains_xy(g, X, Y)
        sub = mask[i0:i1, j0:j1]
        sub[inside & (sub < 0)] = k
    return mask


def area_by_region(mask_bool):
    idx = grid_idx()
    w = np.repeat(_AREA_ROW[:, None], len(_LONG), axis=1)
    sel = mask_bool & (idx >= 0)
    s = pd.Series(np.bincount(idx[sel], weights=w[sel], minlength=48), index=l1_table().region_id)
    return l1_to_both(s, "sum")


def read_shp(path):
    r = shapefile.Reader(str(path))
    fields = [f[0] for f in r.fields[1:]]
    geoms, attrs = [], []
    for sr in r.iterShapeRecords():
        gj = sr.shape.__geo_interface__
        try:
            g = shapely.geometry.shape(gj)
            if not g.is_valid:
                g = shapely.make_valid(g)
        except Exception:  # noqa
            g = None
        geoms.append(g)
        attrs.append(dict(zip(fields, sr.record, strict=True)))
    return geoms, pd.DataFrame(attrs), r.shapeType


def to360(g):
    """Shift geometries given in -180..180 to 0..360, splitting at the 0 meridian."""
    if g is None:
        return g
    minx, _, maxx, _ = g.bounds
    if minx >= 0:
        return g
    west = shapely.clip_by_rect(g, -180, -90, 0, 90)
    east = shapely.clip_by_rect(g, 0, -90, 180, 90)
    west = shapely.affinity.translate(west, xoff=360)
    return shapely.union(west, east)


def gc_len_km(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_MOON_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def lines_length_by_region(geoms):
    lens, lat, lon = [], [], []
    for g in geoms:
        if g is None:
            continue
        parts = getattr(g, "geoms", [g])
        for p in parts:
            c = np.asarray(p.coords)
            if len(c) < 2:
                continue
            L = gc_len_km(c[:-1, 0], c[:-1, 1], c[1:, 0], c[1:, 1])
            lens.append(L)
            lon.append((c[:-1, 0] + c[1:, 0]) / 2)
            lat.append((c[:-1, 1] + c[1:, 1]) / 2)
    L, lat, lon = np.concatenate(lens), np.concatenate(lat), np.mod(np.concatenate(lon), 360)
    idx = l1_index(lat, lon)
    s = pd.Series(
        np.bincount(idx[idx >= 0], weights=L[idx >= 0], minlength=48), index=l1_table().region_id
    )
    return l1_to_both(s, "sum"), float(L.sum())


def points_count_by_region(lat, lon, weights=None):
    idx = l1_index(np.asarray(lat, float), np.mod(np.asarray(lon, float), 360))
    w = np.ones(len(idx)) if weights is None else np.asarray(weights, float)
    s = pd.Series(
        np.bincount(idx[idx >= 0], weights=w[idx >= 0], minlength=48), index=l1_table().region_id
    )
    return l1_to_both(s, "sum")


def series_records(series, var, unit, base, how, coverage=1.0):
    recs, cov = [], []
    for rid, v in series.items():
        if v is None or not np.isfinite(v):
            continue
        r = dict(
            base,
            region_id=rid,
            variable=var,
            value=float(v),
            unit=unit,
            processing_method=how,
            coverage_fraction=coverage
            if np.isscalar(coverage)
            else float(coverage.get(rid, np.nan)),
            n_samples=0,
        )
        recs.append(r)
        cov.append(
            dict(
                region_id=rid,
                variable=var,
                dataset=base["dataset"],
                coverage_fraction=r["coverage_fraction"],
                n_samples=0,
                resolution=base.get("resolution", ""),
                quality=base.get("quality", ""),
                uncertainty=base.get("uncertainty", ""),
            )
        )
    return recs, cov


# ============================================================================ Robbins craters
def process_robbins():
    z = zipfile.ZipFile(RAW / "ROBBINS2018_CRATERS" / "lunar_crater_database_robbins_2018.zip")
    csvs = [n for n in z.namelist() if n.lower().endswith("lunar_crater_database_robbins_2018.csv")]
    df = pd.read_csv(z.open(csvs[0]), low_memory=False)
    (PROCESSED / "robbins_columns.txt").write_text("\n".join(df.columns), encoding="utf-8")
    set_status("ROBBINS2018_CRATERS", "decoded")
    col = {c.upper(): c for c in df.columns}
    lat = df[col.get("LAT_CIRC_IMG", "LAT_CIRC_IMG")].to_numpy(float)
    lon = np.mod(df[col.get("LON_CIRC_IMG", "LON_CIRC_IMG")].to_numpy(float), 360)
    D = df[col.get("DIAM_CIRC_IMG", "DIAM_CIRC_IMG")].to_numpy(float)
    ok = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(D) & (D > 0)
    lat, lon, D = lat[ok], lon[ok], D[ok]
    idx = l1_index(lat, lon)
    area = region_area_series()
    base = meta(
        "ROBBINS2018_CRATERS",
        quality="catalog complete to D~1-2 km (Robbins 2019)",
        resolution="crater catalog D>=1 km (completeness ~1-2 km)",
    )
    recs, cov = [], []
    for dmin in (2, 5, 10, 20, 50):
        cnt = points_count_by_region(lat[D >= dmin], lon[D >= dmin])
        dens = cnt / area.loc[cnt.index] * 1e6
        r, c = series_records(
            dens,
            f"crater_density_ge{dmin}km",
            "craters per 10^6 km2",
            base,
            f"count of Robbins craters with D>={dmin} km (centre in region) / region area",
        )
        recs += r
        cov += c
    l1 = l1_table()
    parent = dict(zip(l1.region_id, l1.parent_region_id, strict=True))
    rid_l1 = np.where(idx >= 0, l1.region_id.to_numpy()[np.clip(idx, 0, None)], None)
    cdf = pd.DataFrame(dict(rid=rid_l1, D=D))
    cdf["rid0"] = cdf.rid.map(parent)
    stats = {}
    for key in ("rid", "rid0"):
        g = cdf[cdf.D >= 2].groupby(key).D
        st = pd.DataFrame(dict(mean=g.mean(), median=g.median(), max=g.max()))

        # power-law cumulative SFD exponent (MLE, Clauset et al. 2009) for 2 <= D <= 100 km
        def mle(x):
            x = x[(x >= 2) & (x <= 100)].to_numpy()
            return (len(x) / np.sum(np.log(x / 2.0))) if len(x) >= 30 else np.nan

        st["b"] = cdf[(cdf.D >= 2)].groupby(key).D.apply(mle)
        # fractional area covered by crater interiors (D>=2 km), sum pi r^2 / area (can exceed 1 with overlaps)
        st["cov"] = cdf[cdf.D >= 2].groupby(key).D.apply(lambda x: np.sum(np.pi * (x / 2) ** 2))
        stats[key] = st
    st = pd.concat([stats["rid"], stats["rid0"]])
    st["cov"] = st["cov"] / area.loc[st.index]
    for c_, var, unit, how in (
        ("mean", "crater_mean_diameter_ge2km", "km", "mean D of craters D>=2 km"),
        ("median", "crater_median_diameter_ge2km", "km", "median D of craters D>=2 km"),
        ("max", "crater_max_diameter", "km", "largest crater centred in region"),
        (
            "b",
            "crater_csfd_cumulative_slope",
            "dimensionless",
            "MLE power-law exponent of cumulative SFD for 2<=D<=100 km (>=30 craters)",
        ),
        (
            "cov",
            "crater_areal_coverage_ge2km",
            "fraction (may exceed 1: overlaps)",
            "sum of crater interior areas (D>=2 km) / region area",
        ),
    ):
        r, c = series_records(st[c_], var, unit, base, how)
        recs += r
        cov += c
    # mean distance from a uniform sample of points to nearest crater centre with D>=5 km and D>=20 km
    rng = np.random.default_rng(7)
    n = 200000
    pz = rng.uniform(-1, 1, n)
    plon = rng.uniform(0, 360, n)
    plat = np.degrees(np.arcsin(pz))
    pidx = l1_index(plat, plon)

    def xyz(la, lo):
        la, lo = np.radians(la), np.radians(lo)
        return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]

    for dmin in (5, 20):
        tree = cKDTree(xyz(lat[D >= dmin], lon[D >= dmin]))
        dch, _ = tree.query(xyz(plat, plon))
        dist = 2 * R_MOON_KM * np.arcsin(np.clip(dch / 2, 0, 1))
        ag = aggregate(dist, np.ones(n), pidx, stats=("mean", "p50", "p95"))
        b = dict(
            base,
            unit="km",
            processing_method=f"distance from 200k uniform random points to nearest centre of a crater D>={dmin} km",
        )
        vm = {"mean": f"dist_to_crater_ge{dmin}km_mean", "p95": f"dist_to_crater_ge{dmin}km_p95"}
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    # depth columns, if present
    depth_cols = [c for c in df.columns if "DEPTH" in c.upper()]
    if depth_cols:
        dc = depth_cols[0]
        dep = pd.to_numeric(df[dc], errors="coerce").to_numpy(float)[ok]
        g = pd.DataFrame(dict(rid=rid_l1, dep=dep, D=D)).dropna()
        g = g[g.D >= 5]
        g["rid0"] = g.rid.map(parent)
        dd = pd.concat([g.groupby("rid").dep.mean(), g.groupby("rid0").dep.mean()])
        r, c = series_records(
            dd, "crater_mean_depth_ge5km", "km", base, f"mean of '{dc}' for craters D>=5 km"
        )
        recs += r
        cov += c
    save_obs("ROBBINS2018_CRATERS", recs, cov)
    set_status("ROBBINS2018_CRATERS", "regionalized")
    return len(recs)


# ============================================================================ LROC shapefiles
def _lroc_shp(dsid, name):
    return read_shp(RAW / dsid / f"{name}_360.shp".lower())


def process_lroc_vectors():
    area = region_area_series()
    recs, cov = [], []
    # --- polygon layers -> area fraction (+count)
    for dsid, name, var in (
        ("LROC_COPERNICAN_CRATERS", "COPERNICAN_CRATERS", "copernican_crater_area_fraction"),
        ("LROC_SWIRLS", "LUNAR_SWIRLS", "swirl_area_fraction"),
    ):
        try:
            geoms, attrs, st = _lroc_shp(dsid, name)
        except Exception as e:  # noqa
            print("  skip", dsid, e)
            continue
        set_status(dsid, "decoded")
        geoms = [to360(g) for g in geoms]
        mask = rasterize(geoms) >= 0
        a = area_by_region(mask)
        base = meta(dsid, quality="vector catalog", resolution="rasterised at 0.1 deg (~3 km)")
        r, c = series_records(
            a / area.loc[a.index],
            var,
            "fraction",
            base,
            "polygon area (0.1-deg rasterisation) / region area",
        )
        recs += r
        cov += c
        cents = [g.representative_point() for g in geoms if g is not None and not g.is_empty]
        cnt = points_count_by_region([p.y for p in cents], [p.x for p in cents])
        r, c = series_records(
            cnt,
            var.replace("area_fraction", "count"),
            "count",
            base,
            "number of polygons (representative point in region)",
        )
        recs += r
        cov += c
        set_status(dsid, "regionalized")
    # --- polylines -> length density
    for dsid, name, var in (
        ("LROC_LOBATE_SCARPS", "LOBATE_SCARPS", "lobate_scarp"),
        ("LROC_WRINKLE_RIDGES", "WRINKLE_RIDGES", "wrinkle_ridge"),
    ):
        try:
            geoms, attrs, st = _lroc_shp(dsid, name)
        except Exception as e:  # noqa
            print("  skip", dsid, e)
            continue
        set_status(dsid, "decoded")
        L, tot = lines_length_by_region(geoms)
        base = meta(dsid, quality="vector catalog", resolution="mapped polylines")
        r, c = series_records(
            L,
            f"{var}_length_km",
            "km",
            base,
            "sum of great-circle segment lengths (segment midpoint in region)",
        )
        recs += r
        cov += c
        r, c = series_records(
            L / area.loc[L.index] * 1e3,
            f"{var}_density",
            "km per 1000 km2",
            base,
            "length / region area",
        )
        recs += r
        cov += c
        set_status(dsid, "regionalized")
    # --- points: new craters, IMPs
    for dsid, name, var in (
        ("LROC_NEW_CRATERS", "GLOBAL_NEW_CRATERS", "new_impact_crater_count"),
        ("LROC_IMPS", "LUNAR_IMP_LOCATIONS", "irregular_mare_patch_count"),
    ):
        try:
            geoms, attrs, st = _lroc_shp(dsid, name)
        except Exception as e:  # noqa
            print("  skip", dsid, e)
            continue
        set_status(dsid, "decoded")
        pts = [g.representative_point() for g in geoms if g is not None and not g.is_empty]
        cnt = points_count_by_region([p.y for p in pts], [p.x for p in pts])
        q = (
            "detections limited to repeat-imaged NAC areas (count is not a rate)"
            if "NEW" in name
            else "catalog"
        )
        base = meta(dsid, quality=q)
        r, c = series_records(cnt, var, "count", base, "number of catalogued features in region")
        recs += r
        cov += c
        set_status(dsid, "regionalized")
    save_obs("LROC_VECTORS", recs, cov)
    return len(recs)


def process_mare_ages():
    dsid = "HIESINGER2011_MARE_AGES"
    geoms, attrs, st = _lroc_shp(dsid, "HIESINGER2011_MARE_AGE_UNITS")
    (PROCESSED / "hiesinger_columns.txt").write_text("\n".join(attrs.columns), encoding="utf-8")
    set_status(dsid, "decoded")
    agecol = next((c for c in attrs.columns if re.search(r"age", c, re.I)), None)
    geoms = [to360(g) for g in geoms]
    lab = rasterize(geoms)
    idx = grid_idx()
    w = np.repeat(_AREA_ROW[:, None], len(_LONG), axis=1)
    # Model_Age is text such as "3.8 Ga": extract the number (unit Ga)
    ages = (
        pd.to_numeric(
            attrs[agecol].astype(str).str.extract(r"([0-9]*\.?[0-9]+)")[0], errors="coerce"
        ).to_numpy(float)
        if agecol
        else np.full(len(geoms), np.nan)
    )
    ages = np.where(ages > 0, ages, np.nan)
    A = np.where(lab >= 0, ages[np.clip(lab, 0, None)], np.nan)
    base = meta(
        dsid,
        unit="Ga",
        quality=f"model ages from crater counts (column '{agecol}')",
        processing_method="area-weighted model age of mapped mare units within region",
    )
    ag = aggregate(A, w, idx, stats=("mean", "min", "max"))
    vm = {
        "mean": "mare_model_age_mean",
        "min": "mare_model_age_youngest",
        "max": "mare_model_age_oldest",
    }
    recs = records_from_agg(ag, vm, base)
    cov = coverage_records(ag, list(vm.values()), base)
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


# ============================================================================ pits
def process_pits():
    dsid = "LROC_PITS"
    df = pd.read_csv(RAW / dsid / "lunar_pit_locations.csv", encoding="latin-1")
    (PROCESSED / "pits_columns.txt").write_text("\n".join(df.columns), encoding="utf-8")
    set_status(dsid, "decoded")
    c = {k.lower(): k for k in df.columns}
    lat = pd.to_numeric(df[c["latitude"]], errors="coerce").to_numpy()
    lon = np.mod(pd.to_numeric(df[c["longitude_360"]], errors="coerce").to_numpy(), 360)
    ok = np.isfinite(lat) & np.isfinite(lon)
    base = meta(dsid, quality="catalog of observed pits; cave connection generally unconfirmed")
    recs, cov = [], []
    r, cv = series_records(
        points_count_by_region(lat[ok], lon[ok]),
        "pit_count",
        "count",
        base,
        "catalogued pits in region",
    )
    recs += r
    cov += cv
    for key, var, how in (
        (
            "overhangs?",
            "pit_overhang_confirmed_count",
            "pits with 'Overhangs?' == 'Y' (confirmed overhang)",
        ),
        (
            "entrance ramp?",
            "pit_entrance_ramp_count",
            "pits with 'Entrance Ramp?' == 'Y' (unbroken slope to floor)",
        ),
    ):
        if var and key in c:
            m = ok & (df[c[key]].astype(str).str.strip().str.upper() == "Y")
            r, cv = series_records(points_count_by_region(lat[m], lon[m]), var, "count", base, how)
            recs += r
            cov += cv
    if "terrain" in c:
        for t in ("mare", "highland", "impact melt"):
            m = ok & df[c["terrain"]].astype(str).str.lower().str.contains(t)
            r, cv = series_records(
                points_count_by_region(lat[m], lon[m]),
                f"pit_count_{t.replace(' ', '_')}",
                "count",
                base,
                f"pits with Terrain containing '{t}'",
            )
            recs += r
            cov += cv
    if "depth_num" in c:
        dep = pd.to_numeric(df[c["depth_num"]], errors="coerce").to_numpy()
        idx = l1_index(lat[ok], lon[ok])
        ag = aggregate(dep[ok], np.ones(ok.sum()), idx, stats=("max", "mean"))
        b = dict(
            base,
            unit="m",
            processing_method="max / mean of catalogued pit depths (shadow measurements)",
        )
        recs += records_from_agg(ag, {"max": "pit_depth_max", "mean": "pit_depth_mean"}, b)
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


# ============================================================================ USGS geologic map
PERIOD_ORDER = ["pN", "N", "I", "E", "C"]


def unit_period(sym):
    s = str(sym).strip()
    if s.startswith("pN"):
        return "pre-Nectarian"
    if s.startswith("N"):
        return "Nectarian"
    if s.startswith("I"):
        return "Imbrian"
    if s.startswith("E"):
        return "Eratosthenian"
    if s.startswith("C"):
        return "Copernican"
    return "other/undivided"


def process_ugm():
    dsid = "USGS_UGM_2020"
    geoms, attrs, st = read_shp(RAW / dsid / "GeoUnits.shp")
    (PROCESSED / "ugm_columns.txt").write_text(
        "\n".join(attrs.columns) + "\n\n" + attrs.head(20).to_string(), encoding="utf-8"
    )
    set_status(dsid, "decoded")
    ucol = next(
        c
        for c in attrs.columns
        if c.lower() in ("firstunit", "first_unit", "unitsymbol", "unit", "symbol", "fstunit")
    )
    sym = attrs[ucol].astype(str).str.strip().to_numpy()
    # explicit attributes of the map: FIRST_Un_1 = stratigraphic period, FIRST_Un_2 = unit type
    period_attr = (
        attrs["FIRST_Un_1"].astype(str).str.strip().to_numpy() if "FIRST_Un_1" in attrs else None
    )
    utype = (
        attrs["FIRST_Un_2"].astype(str).str.strip().to_numpy()
        if "FIRST_Un_2" in attrs
        else np.full(len(sym), "")
    )
    cache = PROCESSED / "ugm_unit_index_0p1deg.npy"
    if cache.exists():
        lab = np.load(cache)
    else:
        # shapefile coordinates may be in degrees (-180..180) or projected metres; detect
        b0 = geoms[0].bounds if geoms[0] is not None else (0, 0, 0, 0)
        if max(abs(b0[0]), abs(b0[2])) > 400:  # metres (equidistant cylindrical on R=1737.4 km)
            k = 180.0 / (math.pi * R_MOON_KM * 1000)
            geoms = [
                shapely.affinity.scale(g, xfact=k, yfact=k, origin=(0, 0))
                if g is not None
                else None
                for g in geoms
            ]
        geoms = [to360(g) for g in geoms]
        lab = rasterize(geoms)
        np.save(cache, lab)
    idx = grid_idx()
    w = np.repeat(_AREA_ROW[:, None], len(_LONG), axis=1)
    covered = (lab >= 0) & (idx >= 0)
    area = region_area_series()
    l1 = l1_table()
    par = l1.set_index("region_id").parent_region_id
    df = pd.DataFrame(
        dict(
            l1=l1.region_id.to_numpy()[idx[covered]],
            sym=sym[lab[covered]],
            w=w[covered],
            utype=utype[lab[covered]],
        )
    )
    df["l0"] = df.l1.map(par)
    if period_attr is not None:
        pmap = {
            "Pre-Nectarian": "pre-Nectarian",
            "Nectarian": "Nectarian",
            "Imbrian": "Imbrian",
            "Eratosthenian": "Eratosthenian",
            "Copernican": "Copernican",
        }
        df["period"] = (
            pd.Series(period_attr[lab[covered]])
            .map(lambda p: pmap.get(p, "transitional/undivided"))
            .to_numpy()
        )
    else:
        df["period"] = df.sym.map(unit_period)
    T = df.utype.str.lower()
    df["is_mare"] = T.str.contains("mare")
    df["is_pyro"] = T.str.contains("dark mantling")
    df["is_dome"] = T.str.contains("dome")
    df["is_crater"] = T.str.contains("crater")
    df["is_basin"] = T.str.contains("basin|formation")
    df["is_plains"] = T.str.contains("plains")
    df["is_terra"] = T.str.contains("terra") & ~df.is_dome
    base = meta(
        dsid,
        quality="1:5M generalised compilation; contacts of variable certainty",
        resolution="1:5,000,000; rasterised at 0.1 deg",
    )
    recs, cov = [], []
    rows = []
    for key in ("l1", "l0"):
        for rid, g in df.groupby(key):
            tot = g.w.sum()
            per = g.groupby("period").w.sum() / tot
            units = g.groupby("sym").w.sum() / tot
            H = -np.sum(units * np.log(units))
            rows.append(
                dict(
                    region_id=rid,
                    coverage=min(1.0, tot / area[rid]),
                    dominant_unit=units.idxmax(),
                    dominant_unit_fraction=units.max(),
                    n_units=len(units),
                    shannon=H,
                    **{
                        f"period_{p}": per.get(p, 0.0)
                        for p in [
                            "pre-Nectarian",
                            "Nectarian",
                            "Imbrian",
                            "Eratosthenian",
                            "Copernican",
                            "transitional/undivided",
                        ]
                    },
                    **{
                        k: g[g[k]].w.sum() / tot
                        for k in (
                            "is_mare",
                            "is_pyro",
                            "is_dome",
                            "is_crater",
                            "is_basin",
                            "is_plains",
                            "is_terra",
                        )
                    },
                    dominant_type=g.groupby("utype").w.sum().idxmax(),
                    top5=";".join(
                        f"{u}:{v:.3f}"
                        for u, v in units.sort_values(ascending=False).head(5).items()
                    ),
                )
            )
    st = pd.DataFrame(rows).set_index("region_id")
    st.to_csv(PROCESSED / "ugm_region_summary.csv")
    for col, var, unit, how in (
        (
            "dominant_unit_fraction",
            "geology_dominant_unit_fraction",
            "fraction",
            "area share of the most extensive map unit",
        ),
        ("n_units", "geology_unit_count", "count", "number of distinct map units"),
        (
            "shannon",
            "geology_unit_diversity_shannon",
            "nats",
            "Shannon entropy of unit area shares",
        ),
        (
            "is_mare",
            "geology_mare_unit_fraction",
            "fraction",
            "area share of units whose type contains 'Mare' (mare basalts, incl. mare domes)",
        ),
        (
            "is_pyro",
            "geology_pyroclastic_dark_mantle_fraction",
            "fraction",
            "area share of 'Dark Mantling Unit' (pyroclastic deposits)",
        ),
        (
            "is_dome",
            "geology_volcanic_dome_fraction",
            "fraction",
            "area share of 'Terra Dome' and 'Mare Dome' units",
        ),
        (
            "is_crater",
            "geology_crater_material_fraction",
            "fraction",
            "area share of crater-material unit types",
        ),
        (
            "is_basin",
            "geology_basin_material_fraction",
            "fraction",
            "area share of basin units and named basin formations",
        ),
        ("is_plains", "geology_plains_fraction", "fraction", "area share of plains units"),
        ("is_terra", "geology_terra_fraction", "fraction", "area share of terra (highland) units"),
    ):
        r, c = series_records(st[col], var, unit, base, how, coverage=st["coverage"].to_dict())
        recs += r
        cov += c
    for p in ["pre-Nectarian", "Nectarian", "Imbrian", "Eratosthenian", "Copernican"]:
        r, c = series_records(
            st[f"period_{p}"],
            f"geology_period_frac_{p.lower().replace('-', '')}",
            "fraction",
            base,
            f"area share of units whose FIRST_Un_1 period is {p}",
            coverage=st["coverage"].to_dict(),
        )
        recs += r
        cov += c
    # categorical (kept in the long table as text in 'value_text')
    for rid, row in st.iterrows():
        for var, val in (
            ("geology_dominant_unit", row.dominant_unit),
            ("geology_dominant_unit_type", row.dominant_type),
            ("geology_top5_units", row.top5),
        ):
            recs.append(
                dict(
                    base,
                    region_id=rid,
                    variable=var,
                    value=np.nan,
                    value_text=str(val),
                    unit="class",
                    coverage_fraction=float(row.coverage),
                    n_samples=0,
                    processing_method="map unit symbol(s) by area share (USGS UGM 2020 'FIRST_Unit' style symbol)",
                )
            )
    save_obs(dsid, recs, cov)
    set_status(dsid, "regionalized")
    return len(recs)


if __name__ == "__main__":
    import sys

    fns = dict(
        robbins=process_robbins,
        lroc=process_lroc_vectors,
        ages=process_mare_ages,
        pits=process_pits,
        ugm=process_ugm,
    )
    for k in sys.argv[1:] or fns:
        print(k, fns[k]())
