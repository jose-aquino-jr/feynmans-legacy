"""Build the hierarchical equal-area lunar region grid (12 L0 + 48 L1 = 60 regions).

Design (documented in reports/regional_processing_report.md):
  * Regions are bounded by parallels and meridians of the planetocentric,
    east-positive Moon ME graticule, so membership of any pixel of any
    PDS cylindrical / polar product is unambiguous and exactly reproducible.
  * Every L0 region has exactly 1/12 of the sphere's area and every L1 region
    exactly 1/48 (area of a lat/lon cell on a sphere = R^2 dlon |sin(phi2)-sin(phi1)|).
  * Poles are NOT split into meridian wedges: each pole is the centre of a single
    circular L1 cap (|lat| >= 73.40 deg), which keeps the lunar polar regions
    (PSRs, Shackleton, Peary...) intact as analysis units.
  * Longitude seam: sector edges fall on 0/72/144/216/288/360 (L0) so the 0/360
    meridian is a boundary, never crossed by a region.

Outputs: outputs/lunar_regions.csv, outputs/lunar_regions.geojson
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from lunar_common import (
    CRS_DESCRIPTION,
    CRS_NAME,
    LAT_CAP_L0,
    LAT_CAP_L1,
    LAT_MID_L1,
    MOON_AREA_KM2,
    OUTPUTS,
    R_MOON_KM,
    write_json,
)


def cell_area(lat_min, lat_max, lon_min, lon_max):
    return (
        R_MOON_KM**2
        * math.radians(lon_max - lon_min)
        * abs(math.sin(math.radians(lat_max)) - math.sin(math.radians(lat_min)))
    )


def cell_centroid(lat_min, lat_max, lon_min, lon_max):
    """Spherical (area-weighted 3-D) centroid projected back to the sphere."""
    # integrate unit vector over the cell analytically
    p1, p2 = math.radians(lat_min), math.radians(lat_max)
    l1, l2 = math.radians(lon_min), math.radians(lon_max)
    # int cos^2(phi) dphi = (phi + sin(phi)cos(phi))/2
    ic2 = ((p2 + math.sin(p2) * math.cos(p2)) - (p1 + math.sin(p1) * math.cos(p1))) / 2
    isc = (math.sin(p2) ** 2 - math.sin(p1) ** 2) / 2
    x = ic2 * (math.sin(l2) - math.sin(l1))
    y = ic2 * (-math.cos(l2) + math.cos(l1))
    z = isc * (l2 - l1)
    n = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / n))
    lon = math.degrees(math.atan2(y, x)) % 360.0
    if abs(lat) > 89.999:
        lon = 0.0
    return lat, lon


def ring(lat_min, lat_max, lon_min, lon_max, step=1.0):
    """Closed polygon ring (lon, lat) densified along parallels; CCW in lon/lat plane."""
    n = max(2, int(math.ceil((lon_max - lon_min) / step)) + 1)
    lons = np.linspace(lon_min, lon_max, n)
    south = [(float(x), lat_min) for x in lons]
    north = [(float(x), lat_max) for x in lons[::-1]]
    pts = south + north + [south[0]]
    return [[round(x, 6), round(y, 6)] for x, y in pts]


def build():
    rows = []
    # ---- L0 -----------------------------------------------------------------
    l0 = []
    l0.append(
        dict(
            code="NPC",
            name="North polar cap",
            lat_min=LAT_CAP_L0,
            lat_max=90.0,
            lon_min=0.0,
            lon_max=360.0,
        )
    )
    for k in range(5):
        l0.append(
            dict(
                code=f"NB{k + 1}",
                name=f"Northern belt sector {k + 1} ({72 * k}-{72 * k + 72}E)",
                lat_min=0.0,
                lat_max=LAT_CAP_L0,
                lon_min=72.0 * k,
                lon_max=72.0 * (k + 1),
            )
        )
    for k in range(5):
        l0.append(
            dict(
                code=f"SB{k + 1}",
                name=f"Southern belt sector {k + 1} ({72 * k}-{72 * k + 72}E)",
                lat_min=-LAT_CAP_L0,
                lat_max=0.0,
                lon_min=72.0 * k,
                lon_max=72.0 * (k + 1),
            )
        )
    l0.append(
        dict(
            code="SPC",
            name="South polar cap",
            lat_min=-90.0,
            lat_max=-LAT_CAP_L0,
            lon_min=0.0,
            lon_max=360.0,
        )
    )

    for i, r in enumerate(l0, start=1):
        r.update(region_id=f"L0_{i:02d}_{r['code']}", level=0, parent_region_id="")
        rows.append(r)

    # ---- L1 -----------------------------------------------------------------
    l1 = []
    for p in rows[:]:
        code = p["code"]
        if code in ("NPC", "SPC"):
            north = code == "NPC"
            inner = dict(
                code=f"{code}-CAP",
                name=("North" if north else "South") + " pole cap (|lat|>=73.40)",
                lat_min=LAT_CAP_L1 if north else -90.0,
                lat_max=90.0 if north else -LAT_CAP_L1,
                lon_min=0.0,
                lon_max=360.0,
            )
            l1.append((p, inner))
            for k in range(3):
                l1.append(
                    (
                        p,
                        dict(
                            code=f"{code}-R{k + 1}",
                            name=("North" if north else "South")
                            + f" polar ring {120 * k}-{120 * k + 120}E",
                            lat_min=LAT_CAP_L0 if north else -LAT_CAP_L1,
                            lat_max=LAT_CAP_L1 if north else -LAT_CAP_L0,
                            lon_min=120.0 * k,
                            lon_max=120.0 * (k + 1),
                        ),
                    )
                )
        else:
            north = code.startswith("NB")
            if north:
                bands = [("LO", 0.0, LAT_MID_L1), ("HI", LAT_MID_L1, LAT_CAP_L0)]
            else:
                bands = [("LO", -LAT_MID_L1, 0.0), ("HI", -LAT_CAP_L0, -LAT_MID_L1)]
            for bcode, a, b in bands:
                for w, (lo, hi) in enumerate(
                    [(p["lon_min"], p["lon_min"] + 36.0), (p["lon_min"] + 36.0, p["lon_max"])]
                ):
                    l1.append(
                        (
                            p,
                            dict(
                                code=f"{code}-{bcode}{'W' if w == 0 else 'E'}",
                                name=f"{p['name'].split(' (')[0]}, {'low' if bcode == 'LO' else 'mid'} latitude, {lo:.0f}-{hi:.0f}E",
                                lat_min=a,
                                lat_max=b,
                                lon_min=lo,
                                lon_max=hi,
                            ),
                        )
                    )
    for j, (p, r) in enumerate(l1, start=1):
        r.update(region_id=f"L1_{j:02d}_{r['code']}", level=1, parent_region_id=p["region_id"])
        rows.append(r)

    df = pd.DataFrame(rows)
    df["area_km2"] = [
        cell_area(r.lat_min, r.lat_max, r.lon_min, r.lon_max) for r in df.itertuples()
    ]
    df["area_fraction"] = df["area_km2"] / MOON_AREA_KM2
    cents = [cell_centroid(r.lat_min, r.lat_max, r.lon_min, r.lon_max) for r in df.itertuples()]
    df["centroid_lat"] = [c[0] for c in cents]
    df["centroid_lon"] = [c[1] for c in cents]
    df["is_polar_cap"] = (df.lon_max - df.lon_min >= 360.0) & (
        (df.lat_max >= 90) | (df.lat_min <= -90)
    )
    df["hemisphere_ns"] = np.where(df.centroid_lat >= 0, "N", "S")
    # near/far side by centroid longitude (sub-Earth point at 0E); caps marked 'polar'
    lon_c = df.centroid_lon
    df["nearside_farside"] = np.where(
        df.is_polar_cap, "polar", np.where((lon_c < 90) | (lon_c > 270), "nearside", "farside")
    )
    df["crs"] = CRS_NAME
    df["reference_radius_km"] = R_MOON_KM
    df["lat_type"] = "planetocentric"
    df["lon_convention"] = "east_positive_0_360"
    cols = [
        "region_id",
        "level",
        "parent_region_id",
        "code",
        "name",
        "lat_min",
        "lat_max",
        "lon_min",
        "lon_max",
        "centroid_lat",
        "centroid_lon",
        "area_km2",
        "area_fraction",
        "is_polar_cap",
        "hemisphere_ns",
        "nearside_farside",
        "crs",
        "reference_radius_km",
        "lat_type",
        "lon_convention",
    ]
    df = df[cols]
    df.to_csv(OUTPUTS / "lunar_regions.csv", index=False, float_format="%.6f")

    feats = []
    for r in df.itertuples():
        feats.append(
            {
                "type": "Feature",
                "id": r.region_id,
                "properties": {
                    c: (getattr(r, c).item() if hasattr(getattr(r, c), "item") else getattr(r, c))
                    for c in cols
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring(r.lat_min, r.lat_max, r.lon_min, r.lon_max)],
                },
            }
        )
    gj = {
        "type": "FeatureCollection",
        "name": "lunar_regions",
        "crs_note": {
            "crs": CRS_NAME,
            "description": CRS_DESCRIPTION,
            "warning": "Coordinates are LUNAR (lon 0-360 E, planetocentric lat). Not WGS84/EPSG:4326. "
            "Polar caps are encoded as lon 0->360 rings closed along the pole; edges between "
            "vertices follow parallels/meridians (densified every 1 deg).",
        },
        "features": feats,
    }
    with open(OUTPUTS / "lunar_regions.geojson", "w", encoding="utf-8") as f:
        json.dump(gj, f)
    return df


def validate(df: pd.DataFrame, n=2_000_000, seed=42):
    from lunar_common import assign_points

    rng = np.random.default_rng(seed)
    z = rng.uniform(-1, 1, n)
    lon = rng.uniform(0, 360, n)
    lat = np.degrees(np.arcsin(z))
    res = {}
    for lev in (0, 1):
        regs = df[df.level == lev].reset_index(drop=True)
        idx = assign_points(lat, lon, regs)
        # overlap check: count points matching >1 region
        cnt = np.zeros(n, dtype=np.int16)
        for r in regs.itertuples():
            in_lat = (lat >= r.lat_min) & ((lat < r.lat_max) | ((r.lat_max >= 90) & (lat <= 90)))
            cnt += (in_lat & (lon >= r.lon_min) & (lon < r.lon_max)).astype(np.int16)
        frac = np.bincount(idx[idx >= 0], minlength=len(regs)) / n
        res[f"L{lev}"] = dict(
            n_regions=len(regs),
            unassigned_points=int((idx < 0).sum()),
            multiply_assigned_points=int((cnt > 1).sum()),
            area_sum_km2=float(regs.area_km2.sum()),
            sphere_area_km2=MOON_AREA_KM2,
            area_sum_rel_error=float(regs.area_km2.sum() / MOON_AREA_KM2 - 1),
            mc_area_fraction_max_abs_dev=float(np.max(np.abs(frac - regs.area_fraction.values))),
        )
    # hierarchy: each L1 bound inside its parent
    l0 = df[df.level == 0].set_index("region_id")
    bad = []
    for r in df[df.level == 1].itertuples():
        p = l0.loc[r.parent_region_id]
        if not (
            r.lat_min >= p.lat_min - 1e-9
            and r.lat_max <= p.lat_max + 1e-9
            and r.lon_min >= p.lon_min - 1e-9
            and r.lon_max <= p.lon_max + 1e-9
        ):
            bad.append(r.region_id)
    child_area = df[df.level == 1].groupby("parent_region_id").area_km2.sum()
    res["hierarchy"] = dict(
        l1_outside_parent=bad,
        children_per_parent=df[df.level == 1].groupby("parent_region_id").size().to_dict(),
        max_parent_child_area_rel_error=float(
            np.max(np.abs(child_area / l0.area_km2.loc[child_area.index] - 1))
        ),
    )
    res["unique_ids"] = bool(df.region_id.is_unique)
    res["n_total"] = len(df)
    write_json(OUTPUTS / "lunar_regions_validation.json", res)
    return res


if __name__ == "__main__":
    d = build()
    print(
        d[
            [
                "region_id",
                "parent_region_id",
                "lat_min",
                "lat_max",
                "lon_min",
                "lon_max",
                "area_km2",
            ]
        ].to_string()
    )
    print(json.dumps(validate(d), indent=1))
