"""Operational derived variables (explicit criteria, no weighted composite indices).

ops_landing_joint_fraction : area fraction of 16 px/deg cells (|lat|<=60) where BOTH
    LOLA 240 m slope < 10 deg AND Diviner rock abundance < 1 %  (pixel-level co-registration:
    RA 32 px/deg averaged 2x2 to the LOLA 16 px/deg grid).  Thresholds are stated, not tuned.
dist_to_psr / dist_to_pit / dist_to_hiti : great-circle distances from every 4 px/deg cell
    centre of a region to the nearest mapped feature (LOLA PSR pixel; catalogued pit;
    WAC TiO2 >= 6 wt% sampled pixel).  Region statistics: min, median, mean.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lunar_common import PROCESSED, R_MOON_KM, RAW
from proc_common import meta, read_pds_img
from regionalize import (
    aggregate,
    coverage_records,
    cyl_pixel_area,
    l1_index,
    records_from_agg,
    save_obs,
    set_status,
)
from scipy.spatial import cKDTree


def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def chord_to_km(d):
    return 2 * R_MOON_KM * np.arcsin(np.clip(d / 2, 0, 1))


def main():
    recs, cov = [], []
    # ---------------------------------------------------------------- joint landing criterion
    s240 = np.load(PROCESSED / "ldsm16_slope240_deg.npy")  # 2880 x 5760, 90..-90
    ra, m, _ = read_pds_img("DIVINER_RA", "dgdr_ra_avg_cyl_032_img.img")  # 3840 x 11520, 60..-60
    ra16 = ra.reshape(1920, 2, 5760, 2).mean(axis=(1, 3))
    s = s240[480:2400]
    lat = 60 - (np.arange(1920) + 0.5) / 16
    lon = (np.arange(5760) + 0.5) / 16
    ok = np.isfinite(s) & np.isfinite(ra16)
    joint = np.where(ok, ((s < 10) & (ra16 < 0.01)).astype(float), np.nan)
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    idx = l1_index(LAT, LON)
    area = np.repeat(cyl_pixel_area(lat, 16)[:, None], 5760, axis=1)
    b = meta(
        "LOLA_LDSM_16",
        dataset="DERIVED_OPERATIONS",
        unit="fraction",
        product="derived from LOLA LDSM_16 + Diviner RA (co-registered at 16 px/deg)",
        resolution="16 px/deg (1.9 km) cells; |lat| <= 60 (Diviner RA limit)",
        quality="criterion-based; sub-km hazards not resolved",
        processing_method="area fraction where LOLA 240 m slope < 10 deg AND Diviner rock abundance < 0.01",
    )
    ag = aggregate(joint, area, idx, stats=("mean",))
    recs += records_from_agg(ag, {"mean": "ops_landing_joint_fraction"}, b)
    cov += coverage_records(ag, ["ops_landing_joint_fraction"], b)

    # ---------------------------------------------------------------- distances from 4 px/deg cell centres
    lat4 = 90 - (np.arange(720) + 0.5) / 4
    lon4 = (np.arange(1440) + 0.5) / 4
    L4, O4 = np.meshgrid(lat4, lon4, indexing="ij")
    idx4 = l1_index(L4, O4)
    w4 = np.repeat(cyl_pixel_area(lat4, 4)[:, None], 1440, axis=1)
    P = xyz(L4.ravel(), O4.ravel())
    targets = {}
    # PSR pixels (official LOLA, sampled 480 m) - reuse polar reader
    from proc_illumination import _both

    a, la, lo, _ = _both("LOLA_LPSR_65", "lpsr_65{}_240m_201608.img")
    sel = np.isfinite(a) & (a > 0.5)
    targets["psr"] = (
        la[sel],
        lo[sel],
        "LOLA LPSR 240 m PSR pixels (|lat| >= ~55-65 deg mapped domain)",
    )
    pits = pd.read_csv(RAW / "LROC_PITS" / "lunar_pit_locations.csv", encoding="latin-1")
    c = {k.lower(): k for k in pits.columns}
    targets["pit"] = (
        pd.to_numeric(pits[c["latitude"]], errors="coerce").dropna().to_numpy(),
        np.mod(pd.to_numeric(pits[c["longitude_360"]], errors="coerce").dropna().to_numpy(), 360),
        "LROC catalogued pits (Wagner & Robinson)",
    )
    from proc_composition import load_wac_tio2_tiles

    tiles, _ = load_wac_tio2_tiles()
    if tiles:
        las, los = [], []
        for la_, lo_, va in tiles:
            ii, jj = np.where((va >= 6) & (va <= 15))
            las.append(la_[ii])
            los.append(lo_[jj])
        targets["hiti"] = (
            np.concatenate(las),
            np.concatenate(los),
            "LROC WAC TiO2 >= 6 wt% pixels (sampled lines, |lat|<=70)",
        )
    for key, (tla, tlo, desc) in targets.items():
        if len(tla) == 0:
            continue
        tree = cKDTree(xyz(tla, tlo))
        d, _ = tree.query(P, k=1)
        dist = chord_to_km(d).reshape(720, 1440)
        b = meta(
            "LOLA_LPSR_65",
            dataset="DERIVED_OPERATIONS",
            unit="km",
            product=f"distance to {desc}",
            resolution="from 4 px/deg cell centres",
            quality="distance to MAPPED features only (unmapped ones ignored)",
            processing_method=f"great-circle distance from each 7.6 km cell centre to nearest {desc}",
        )
        ag = aggregate(dist, w4, idx4, stats=("mean", "min", "p50"))
        vm = {
            "mean": f"dist_to_{key}_km_mean",
            "min": f"dist_to_{key}_km_min",
            "p50": f"dist_to_{key}_km_p50",
        }
        recs += records_from_agg(ag, vm, b)
        cov += coverage_records(ag, list(vm.values()), b)
    save_obs("DERIVED_OPERATIONS", recs, cov)
    set_status("DERIVED_OPERATIONS", "regionalized")
    return len(recs)


if __name__ == "__main__":
    print(main())
