"""Composition, mineralogy, volatiles (LP), maturity and radar processors."""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from dataset_registry import by_id
from lunar_common import PROCESSED, R_MOON_KM, RAW
from lunar_io import (
    fetch_text,
    img_meta_from_label,
    parse_pds3_label,
    remote_rows,
    save_manifest_entry,
)
from proc_common import meta, proj_num
from regionalize import (
    aggregate,
    coverage_records,
    cyl_grid_from_label,
    cyl_pixel_area,
    frac_above,
    l1_index,
    records_from_agg,
    save_obs,
    set_status,
)

OX = ["MgO", "Al2O3", "SiO2", "CaO", "TiO2", "FeO"]
MOLAR = {
    "MgO": 40.304,
    "Al2O3": 101.961,
    "SiO2": 60.084,
    "CaO": 56.077,
    "TiO2": 79.866,
    "FeO": 71.844,
}
NOX = {"MgO": 1, "Al2O3": 3, "SiO2": 2, "CaO": 1, "TiO2": 2, "FeO": 1}


def _cell_area(lat1, lat2, lon1, lon2):
    return (
        R_MOON_KM**2
        * np.radians(lon2 - lon1)
        * np.abs(np.sin(np.radians(lat2)) - np.sin(np.radians(lat1)))
    )


def process_lp_grs():
    f = RAW / "LP_GRS_ELEM_2DEG" / "lpgrs_high1_elem_abundance_2deg.tab"
    cols = (
        ["pix", "lat1", "lat2", "lon1", "lon2", "am", "nden"]
        + ["w_" + o for o in OX]
        + ["k_ppm", "th_ppm", "u_ppm"]
    )
    raw = np.loadtxt(f)
    df = pd.DataFrame(raw[:, :16], columns=cols)
    # error matrix: 45 upper-triangle terms E[i,j], i<=j, i,j = 0..8 (order MgO,Al2O3,SiO2,CaO,TiO2,FeO,K,Th,U)
    E = raw[:, 16:61]
    pos, k = {}, 0
    for i in range(9):
        for j in range(i, 9):
            pos[(i, j)] = k
            k += 1
    sig = {
        n: np.sqrt(np.clip(E[:, pos[(i, i)]], 0, None)) for i, n in enumerate(OX + ["K", "Th", "U"])
    }
    set_status("LP_GRS_ELEM_2DEG", "decoded")
    lat = (df.lat1 + df.lat2).to_numpy() / 2
    lon = np.mod((df.lon1 + df.lon2).to_numpy() / 2, 360)
    # pixels that span the full longitude range (polar caps) -> centre at pole
    w = _cell_area(df.lat1, df.lat2, df.lon1, df.lon2).to_numpy()
    idx = l1_index(lat, lon)
    base = meta(
        "LP_GRS_ELEM_2DEG",
        resolution="2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM",
        quality="good (published, peer-reviewed); low-abundance elements noisy",
    )
    recs, cov = [], []
    for n in OX:
        v = df["w_" + n].to_numpy() * 100.0
        b = dict(
            base,
            unit="wt%",
            processing_method=f"area-weighted mean of LP GRS {n} weight fraction x100",
            uncertainty="sigma from sqrt(diag) of published error matrix (regional mean of per-pixel sigma)",
        )
        ag = aggregate(v, w, idx, stats=("mean", "std", "min", "max", "p05", "p95"))
        ags = aggregate(sig[n] * 100.0, w, idx, stats=("mean",))
        ag["sig"] = ags["mean"]
        var = f"{n.lower()}_wt_lp"
        vm = {
            "mean": var,
            "std": f"{var}_std",
            "min": f"{var}_min",
            "max": f"{var}_max",
            "p05": f"{var}_p05",
            "p95": f"{var}_p95",
            "sig": f"{var}_sigma",
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    for n, col in (("K", "k_ppm"), ("Th", "th_ppm"), ("U", "u_ppm")):
        v = df[col].to_numpy()
        b = dict(base, unit="ppm", processing_method=f"area-weighted LP GRS {n}")
        ag = aggregate(v, w, idx, stats=("mean", "max", "p95"))
        ag["sig"] = aggregate(sig[n], w, idx, stats=("mean",))["mean"]
        var = f"{n.lower()}_ppm_lp"
        vm = {"mean": var, "max": f"{var}_max", "p95": f"{var}_p95", "sig": f"{var}_sigma"}
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    # derived: Mg#, stoichiometric bound oxygen, average atomic mass
    mgn = (df.w_MgO / MOLAR["MgO"]) / (df.w_MgO / MOLAR["MgO"] + df.w_FeO / MOLAR["FeO"]) * 100
    oxy = sum(df["w_" + o] * NOX[o] * 15.999 / MOLAR[o] for o in OX) * 100
    for v, var, unit, how in (
        (mgn, "mg_number_lp", "molar %", "Mg# = 100 Mg/(Mg+Fe) molar, from LP MgO and FeO"),
        (
            oxy,
            "oxygen_bound_wt_lp",
            "wt%",
            "stoichiometric oxygen bound in the six major oxides "
            "(sum w_i * nO*16/M_i); presence/concentration only, not extractable yield",
        ),
        (df.am, "avg_atomic_mass_lp", "g/mol", "LP GRS average atomic mass"),
    ):
        b = dict(base, unit=unit, processing_method=how)
        ag = aggregate(np.asarray(v, float), w, idx, stats=("mean", "min", "max"))
        vm = {"mean": var, "min": f"{var}_min", "max": f"{var}_max"}
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    save_obs("LP_GRS_ELEM_2DEG", recs, cov)
    set_status("LP_GRS_ELEM_2DEG", "regionalized")
    return len(recs)


def process_lp_halfdeg():
    d = RAW / "LP_HALFDEG_H_FE_TH"
    recs, cov = [], []
    specs = (
        (
            "hydrogenhd.txt",
            "hydrogen_ppm_lp",
            "ppm H (by weight)",
            "LP NS epithermal-neutron H (Feldman 2001); top ~1 m; assumes uniform with depth",
        ),
        ("ironhd.txt", "feo_wt_lp_halfdeg", "wt% FeO", "LP GRS FeO half-degree (Lawrence 2002)"),
        ("thoriumhd.txt", "th_ppm_lp_halfdeg", "ppm Th", "LP GRS Th half-degree (Lawrence 2003)"),
    )
    for fn, var, unit, how in specs:
        t = pd.read_csv(d / fn, comment="#", header=None, skipinitialspace=True)
        a = t.apply(pd.to_numeric, errors="coerce").to_numpy(
            float
        )  # Fortran overflow '*****' -> NaN
        n_over = int(np.isnan(a[:, 4]).sum())
        lat = (a[:, 0] + a[:, 1]) / 2
        lon = np.mod((a[:, 2] + a[:, 3]) / 2, 360)
        v = a[:, 4].astype(float)
        # Negative bins are counting-statistics noise around near-zero true abundances; removing them would
        # bias regional means upward, so they are KEPT in the statistics and only counted in the quality field.
        n_neg = int((v < 0).sum())
        w = _cell_area(a[:, 0], a[:, 1], a[:, 2], a[:, 3])
        idx = l1_index(lat, lon)
        b = meta(
            "LP_HALFDEG_H_FE_TH",
            unit=unit.split(" ")[0] if unit.startswith("ppm") else "wt%",
            product=f"LP special product {fn}",
            processing_method=f"area-weighted stats of {how}",
            quality=f"smoothed; not a formal PDS archive product; {n_over} overflow ('*****') bins invalid; "
            f"{n_neg} of {len(v)} bins negative (noise, kept)",
            source=f"{by_id()['LP_HALFDEG_H_FE_TH']['urls'][0].rsplit('/', 1)[0]}/{fn}",
        )
        # min of a noisy field (negative bins kept) is not physical -> report p05 instead of min
        ag = aggregate(v, w, idx, stats=("mean", "std", "p05", "max", "p95"))
        vm = {
            "mean": var,
            "std": f"{var}_std",
            "p05": f"{var}_p05",
            "max": f"{var}_max",
            "p95": f"{var}_p95",
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    save_obs("LP_HALFDEG_H_FE_TH", recs, cov)
    set_status("LP_HALFDEG_H_FE_TH", "regionalized")
    return len(recs)


# ----------------------------------------------------------------------------- LROC WAC TiO2
TIO2_BLOCK, TIO2_PERIOD = (
    8,
    64,
)  # 8 contiguous lines every 64 (1/8 of lines, few large requests: S3 rate limit)
TIO2_STRIDE = TIO2_PERIOD // TIO2_BLOCK  # area weight per sampled line


def load_wac_tio2_tiles():
    """Per-tile cached samples: list of (lat rows, lon cols, values), and pixel size (deg)."""
    tdir = PROCESSED / "wac_tio2_tiles"
    tiles, res = [], None
    for f in sorted(tdir.glob("*.npz")):
        t = np.load(f)
        tiles.append((t["la"], t["lo"], t["va"]))
        res = float(t["res"])
    return tiles, res


def process_wac_tio2():
    ds = by_id()["LROC_WAC_TIO2"]
    n_img = len([x for x in ds["urls"] if x.endswith(".IMG")])
    if len(load_wac_tio2_tiles()[0]) < n_img:
        lats, lons, vals = [], [], []
        tdir = PROCESSED / "wac_tio2_tiles"
        tdir.mkdir(exist_ok=True)
        for u in [x for x in ds["urls"] if x.endswith(".IMG")]:
            tcache = tdir / (u.rsplit("/", 1)[-1] + ".npz")
            if tcache.exists():
                t = np.load(tcache)
                lats.append(t["la"])
                lons.append(t["lo"])
                vals.append(t["va"])
                res = float(t["res"])
                continue
            xml = fetch_text(u[:-4] + ".xml")
            offs = [int(x) for x in re.findall(r'<offset unit="byte">(\d+)</offset>', xml)]
            el = [int(x) for x in re.findall(r"<elements>(\d+)</elements>", xml)]
            nl, ns = el[0], el[1]
            res = float(
                re.search(r'pixel_resolution_x unit="deg/pixel">([0-9.eE+-]+)<', xml).group(1)
            )
            ulx = float(re.search(r'upperleft_corner_x unit="m">([0-9.eE+-]+)<', xml).group(1))
            uly = float(re.search(r'upperleft_corner_y unit="m">([0-9.eE+-]+)<', xml).group(1))
            west = float(
                re.search(r'west_bounding_coordinate unit="deg">([0-9.eE+-]+)<', xml).group(1)
            )
            m_per_deg = R_MOON_KM * 1000 * np.pi / 180
            lat0 = uly / m_per_deg  # north edge of first line
            # Label quirk (verified on all 8 tiles): central meridian is 0 but upperleft_corner_x is stored as
            # -(west) - half pixel. The true west edge of the first sample is therefore west - half pixel.
            half = abs(ulx / m_per_deg) - west
            assert abs(half - res / 2) < 1e-3, (u, half, res)
            lon0 = west - half
            rows = [
                r for b0 in range(0, nl, TIO2_PERIOD) for r in range(b0, min(b0 + TIO2_BLOCK, nl))
            ]
            got = remote_rows(
                u, "LROC_WAC_TIO2", offs[-1], ns * 4, rows, nconn=1, max_run=TIO2_BLOCK
            )
            arr = (
                np.frombuffer(b"".join(got[r] for r in rows), dtype="<f4")
                .reshape(len(rows), ns)
                .astype(np.float32)
            )
            arr = arr.copy()
            arr[(arr < -1e30) | ~np.isfinite(arr)] = np.nan
            la = lat0 - (np.array(rows) + 0.5) * res
            lo_raw = lon0 + (np.arange(ns) + 0.5) * res
            # tiles overlap by ~1 pixel: keep only pixel centres inside the nominal tile bounds (no double counting)
            north = float(
                re.search(r'north_bounding_coordinate unit="deg">([0-9.eE+-]+)<', xml).group(1)
            )
            south = float(
                re.search(r'south_bounding_coordinate unit="deg">([0-9.eE+-]+)<', xml).group(1)
            )
            east = float(
                re.search(r'east_bounding_coordinate unit="deg">([0-9.eE+-]+)<', xml).group(1)
            )
            arr[(la < south) | (la >= north), :] = np.nan
            arr[:, (lo_raw < west) | (lo_raw >= east)] = np.nan
            lo = np.mod(lo_raw, 360)
            np.savez_compressed(tcache, la=la, lo=lo, va=arr, res=res)
            lats.append(la)
            lons.append(lo)
            vals.append(arr)
            print(f"  {u.rsplit('/', 1)[-1]}: {len(rows)} rows", flush=True)
    tiles, res = load_wac_tio2_tiles()
    V, W, I = [], [], []
    for la, lo, va in tiles:
        # tiles overlap by ~1 pixel at edges; keep pixel centres inside the nominal tile bounds only
        LAT, LON = np.meshgrid(la, lo, indexing="ij")
        a = np.repeat((cyl_pixel_area(la, 1 / res) * TIO2_STRIDE)[:, None], len(lo), axis=1)
        V.append(va.ravel())
        W.append(a.ravel())
        I.append(l1_index(LAT, LON).ravel())
    V, W, I = np.concatenate(V), np.concatenate(W), np.concatenate(I)
    set_status("LROC_WAC_TIO2", "processed")
    base = meta(
        "LROC_WAC_TIO2",
        resolution="~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)",
        quality="values <2 wt% set to 1 wt% by producer (below detection); >15 wt% untrusted (producer note)",
    )
    trusted = np.where(V <= 15, V, np.nan)
    recs, cov = [], []
    b = dict(
        base,
        unit="wt%",
        processing_method="area-weighted stats of WAC TiO2 (producer's BDL convention kept: <2 -> 1)",
    )
    ag = aggregate(
        trusted,
        W,
        I,
        stats=("mean", "p50", "p95", "max"),
        extra={"det": frac_above(1.999), "hiTi": frac_above(6.0)},
    )
    vm = {
        "mean": "tio2_wt_wac",
        "p50": "tio2_wt_wac_p50",
        "p95": "tio2_wt_wac_p95",
        "max": "tio2_wt_wac_max",
    }
    recs += records_from_agg(ag, vm, b)
    fm = {"det": "tio2_wac_area_frac_ge2wt", "hiTi": "tio2_wac_area_frac_gt6wt"}
    recs += records_from_agg(
        ag,
        fm,
        dict(
            b,
            unit="fraction",
            processing_method="area fraction above threshold "
            "(2 wt% = detection limit; 6 wt% = conventional high-Ti mare basalt boundary)",
        ),
    )
    cov += coverage_records(ag, list(vm.values()) + list(fm.values()), b)
    save_obs("LROC_WAC_TIO2", recs, cov)
    set_status("LROC_WAC_TIO2", "regionalized")
    return len(recs)


# ----------------------------------------------------------------------------- Kaguya MI minerals
KMI_STRIDE = 256  # 0.5 deg line spacing at 512 px/deg
KMI_COLBIN = 8


def _read_kmi(url):
    import rasterio
    from rasterio.windows import Window

    rows = list(range(KMI_STRIDE // 2, 51200, KMI_STRIDE))
    env = dict(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_MAX_RETRY="5",
        GDAL_HTTP_RETRY_DELAY="3",
    )

    def job(chunk):
        out = {}
        with rasterio.Env(**env):
            s = rasterio.open("/vsicurl/" + url)
            nodata = s.nodata
            for r in chunk:
                for attempt in range(8):
                    try:
                        a = s.read(1, window=Window(0, r, s.width, 1))[0].astype(np.float32)
                        break
                    except Exception:  # noqa  transient HTTP failure: reopen the handle and retry
                        if attempt == 7:
                            raise
                        time.sleep(5 * (attempt + 1))
                        s.close()
                        s = rasterio.open("/vsicurl/" + url)
                a[(a == nodata) | (a < -1e30) | ~np.isfinite(a)] = np.nan
                with np.errstate(all="ignore"):
                    out[r] = np.nanmean(a.reshape(-1, KMI_COLBIN), axis=1)
            s.close()
        return out

    chunks = [rows[i::6] for i in range(6)]
    res = {}
    with ThreadPoolExecutor(6) as ex:
        for d in ex.map(job, chunks):
            res.update(d)
    arr = np.stack([res[r] for r in rows])
    h = hashlib.sha256(arr.tobytes()).hexdigest()
    return rows, arr, h


def process_kaguya():
    ds = by_id()["KAGUYA_MI_MINERALS"]
    recs, cov = [], []
    for u in ds["urls"]:
        name = re.search(r"MineralDeconv_(\w+?)Percent", u).group(1).lower()
        cache = PROCESSED / f"kaguya_mi_{name}_rows.npz"
        if cache.exists():
            z = np.load(cache)
            rows, arr = list(z["rows"]), z["arr"]
        else:
            t0 = time.time()
            rows, arr, h = _read_kmi(u)
            np.savez_compressed(cache, rows=rows, arr=arr)
            save_manifest_entry(
                f"KAGUYA_MI_MINERALS:{u.rsplit('/', 1)[-1]}",
                dict(
                    dataset_id="KAGUYA_MI_MINERALS",
                    url=u,
                    mode="remote_row_sample",
                    row_stride=KMI_STRIDE,
                    first_row=rows[0],
                    column_block_mean=KMI_COLBIN,
                    sha256_of_decoded_sample=h,
                    retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
                    seconds=round(time.time() - t0, 1),
                ),
            )
            print(f"  {name}: {arr.shape} in {time.time() - t0:.0f}s", flush=True)
        res = 512.0
        lat = 50.0 - (np.array(rows) + 0.5) / res
        lon = np.mod(-180.0 + (np.arange(arr.shape[1]) * KMI_COLBIN + KMI_COLBIN / 2) / res, 360)
        LAT, LON = np.meshgrid(lat, lon, indexing="ij")
        w = np.repeat(
            (cyl_pixel_area(lat, res) * KMI_STRIDE * KMI_COLBIN)[:, None], len(lon), axis=1
        )
        idx = l1_index(LAT, LON)
        var = {
            "plagioclase": "plagioclase_wt_kmi",
            "olivine": "olivine_wt_kmi",
            "orthopyroxene": "lowca_pyroxene_wt_kmi",
            "clinopyroxene": "highca_pyroxene_wt_kmi",
        }[name]
        b = meta(
            "KAGUYA_MI_MINERALS",
            unit="wt%",
            product=u.rsplit("/", 1)[-1],
            resolution="59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means",
            quality="+/-50 deg only; model-derived abundances (Hapke); file values are fractions 0-1, converted x100",
            processing_method="area-weighted stats of Kaguya MI mineral abundance (Lemelin et al.)",
            source=u,
        )
        # The GeoTIFF stores weight FRACTIONS (0-1; plagioclase median 0.81) despite the "Percent" file name:
        # converted to wt% (x100) for consistency with LP GRS oxides.
        ag = aggregate(arr * 100.0, w, idx, stats=("mean", "std", "p05", "p50", "p95"))
        vm = {
            s: (var if s == "mean" else f"{var}_{s}") for s in ("mean", "std", "p05", "p50", "p95")
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
        set_status("KAGUYA_MI_MINERALS", "processed")
    save_obs("KAGUYA_MI_MINERALS", recs, cov)
    set_status("KAGUYA_MI_MINERALS", "regionalized")
    return len(recs)


# ----------------------------------------------------------------------------- npFe (Trang 2020)
def process_npfe():
    d = RAW / "TRANG2020_NPFE"
    xml = (d / "kaguya_mi_derived_30ppd_npfe.xml").read_text(errors="replace")
    el = [int(x) for x in re.findall(r"<elements>(\d+)</elements>", xml)]
    dt = re.search(r"<data_type>(\w+)</data_type>", xml).group(1)
    dtype = {"IEEE754LSBSingle": "<f4", "IEEE754MSBSingle": ">f4"}[dt]
    offs = [int(x) for x in re.findall(r'<offset unit="byte">(\d+)</offset>', xml)]
    nl, ns = el[0], el[1]
    a = (
        np.fromfile(
            d / "kaguya_mi_derived_30ppd_npfe.img",
            dtype=dtype,
            offset=offs[-1] if offs else 0,
            count=nl * ns,
        )
        .reshape(nl, ns)
        .astype(np.float32)
    )
    mc = re.search(r"<missing_constant>([^<]+)</missing_constant>", xml)
    a[~np.isfinite(a) | (a < -1e30)] = np.nan
    if mc:
        try:
            a[a == np.float32(float(mc.group(1)))] = np.nan
        except ValueError:
            pass

    def g(tag):
        m = re.search(rf"<cart:{tag}\s[^>]*>\s*([-0-9.eE+]+)\s*<", xml, re.S)
        return float(m.group(1)) if m else None

    # geometry from the Geo_Transformation (bounding coordinates in this label are inconsistent: W=180, E=-180)
    m_per_deg = R_MOON_KM * 1000 * np.pi / 180
    res_deg = g("pixel_resolution_x") / m_per_deg
    west = g("upperleft_corner_x") / m_per_deg
    north = g("upperleft_corner_y") / m_per_deg
    res = 1.0 / res_deg
    assert abs(res - 30) < 0.01 and abs(north - 60) < 0.01, (res, north)
    lat, lon = cyl_grid_from_label(nl, ns, res, north, west)
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    w = np.repeat(cyl_pixel_area(lat, res)[:, None], ns, axis=1)
    set_status("TRANG2020_NPFE", "decoded")
    b = meta(
        "TRANG2020_NPFE",
        unit="wt%",
        processing_method="area-weighted stats of nanophase Fe0 abundance (space-weathering maturity)",
        quality=f"grid {nl}x{ns} (30 px/deg, +/-60), geometry from PDS4 Geo_Transformation; "
        "NoData -3.4e38; unit wt% per Trang & Lucey 2019 (label gives no unit)",
    )
    ag = aggregate(a, w, idx, stats=("mean", "std", "p05", "p50", "p95"))
    vm = {
        s: ("npfe_wt" if s == "mean" else f"npfe_wt_{s}")
        for s in ("mean", "std", "p05", "p50", "p95")
    }
    recs = records_from_agg(ag, vm, b)
    save_obs("TRANG2020_NPFE", recs, coverage_records(ag, list(vm.values()), b))
    set_status("TRANG2020_NPFE", "regionalized")
    return len(recs)


# ----------------------------------------------------------------------------- Mini-RF CPR
MRF_STRIDE = 4


def process_minirf():
    ds = by_id()["MINIRF_CPR_32"]
    img = ds["urls"][0]
    lbl = parse_pds3_label(fetch_text(ds["urls"][1]))
    m = img_meta_from_label(lbl)
    rows = list(range(0, m["lines"], MRF_STRIDE))
    cache = PROCESSED / "minirf_cpr_rows.npy"
    if cache.exists():
        arr = np.load(cache)
    else:
        got = remote_rows(img, "MINIRF_CPR_32", m["header_bytes"], m["samples"] * 4, rows)
        arr = (
            np.frombuffer(b"".join(got[r] for r in rows), dtype=m["dtype"])
            .reshape(len(rows), m["samples"])
            .astype(np.float32)
        )
        np.save(cache, arr)
    arr = arr.copy()
    arr[~np.isfinite(arr) | (arr < -1e30)] = np.nan
    res = proj_num(m, "MAP_RESOLUTION")
    lat_all, lon = cyl_grid_from_label(
        m["lines"],
        m["samples"],
        res,
        proj_num(m, "MAXIMUM_LATITUDE"),
        proj_num(m, "WESTERNMOST_LONGITUDE"),
    )
    lat = lat_all[rows]
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    w = np.repeat((cyl_pixel_area(lat, res) * MRF_STRIDE)[:, None], len(lon), axis=1)
    # physically CPR >= 0; values > 5 treated as artefacts (counted in QA, not used)
    neg = np.sum(arr < 0)
    big = np.sum(arr > 5)
    arr[(arr < 0) | (arr > 5)] = np.nan
    set_status("MINIRF_CPR_32", "processed")
    b = meta(
        "MINIRF_CPR_32",
        unit="ratio",
        resolution="32 px/deg; every 4th line sampled",
        quality=f"uncontrolled mosaic; {int(neg)} negative and {int(big)} >5 values excluded",
        processing_method="area-weighted stats of S-band CPR (SC/OC)",
    )
    ag = aggregate(arr, w, idx, stats=("mean", "std", "p50", "p95"), extra={"hi": frac_above(1.0)})
    vm = {
        "mean": "radar_cpr_mean",
        "std": "radar_cpr_std",
        "p50": "radar_cpr_p50",
        "p95": "radar_cpr_p95",
    }
    recs = records_from_agg(ag, vm, b)
    recs += records_from_agg(
        ag,
        {"hi": "radar_cpr_area_frac_gt1"},
        dict(
            b,
            unit="fraction",
            processing_method="area fraction with CPR > 1 (very rough or volume-scattering surfaces)",
        ),
    )
    save_obs(
        "MINIRF_CPR_32",
        recs,
        coverage_records(ag, list(vm.values()) + ["radar_cpr_area_frac_gt1"], b),
    )
    set_status("MINIRF_CPR_32", "regionalized")
    return len(recs)


if __name__ == "__main__":
    import sys

    fns = dict(
        lp=process_lp_grs,
        lphd=process_lp_halfdeg,
        tio2=process_wac_tio2,
        kmi=process_kaguya,
        npfe=process_npfe,
        minirf=process_minirf,
    )
    for k in sys.argv[1:] or fns:
        t0 = time.time()
        print(k, fns[k](), f"{time.time() - t0:.0f}s", flush=True)
