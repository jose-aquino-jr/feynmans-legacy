"""Assemble the final products from data/processed/obs/*.parquet:

outputs/lunar_observations.parquet   (long, fully traceable)
outputs/lunar_region_features.parquet (wide, one row per region, column metadata)
outputs/region_variable_coverage.csv
outputs/variable_summary.csv
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dataset_registry import by_id
from lunar_common import CRS_DESCRIPTION, CRS_NAME, OUTPUTS, load_regions
from regionalize import OBS_DIR

LONG_COLS = [
    "region_id",
    "variable",
    "value",
    "value_text",
    "unit",
    "dataset",
    "mission",
    "instrument",
    "product",
    "version",
    "resolution",
    "observation_date",
    "time_period",
    "quality",
    "uncertainty",
    "coverage_fraction",
    "n_samples",
    "processing_method",
    "source",
]

# variable-name prefix -> thematic group (ordering of the wide table)
GROUPS = [
    (
        "topography",
        (
            "elevation_",
            "relief_",
            "hypsometric",
            "slope_km",
            "aspect_",
            "curvature_",
            "concave_",
            "convex_",
            "tpi_",
            "slope_240m",
            "roughness_",
            "lola_",
        ),
    ),
    (
        "craters_boulders",
        ("crater_", "dist_to_crater", "copernican_", "new_impact", "rock_abundance"),
    ),
    ("geology", ("geology_", "mare_model_age", "lobate_", "wrinkle_", "irregular_mare")),
    (
        "composition",
        (
            "feo_",
            "tio2_",
            "mgo_",
            "al2o3_",
            "sio2_",
            "cao_",
            "k_ppm",
            "th_ppm",
            "u_ppm",
            "mg_number",
            "avg_atomic",
            "christiansen",
        ),
    ),
    ("mineralogy", ("plagioclase_", "olivine_", "lowca_", "highca_")),
    ("regolith", ("npfe_", "regolith_temp", "radar_cpr")),
    ("temperature", ("tbol_", "annual_mean_surface", "annual_max_surface", "heat_flow")),
    (
        "illumination",
        (
            "illum",
            "illumination_",
            "insolation_",
            "solar_",
            "longest_dark",
            "never_lit",
            "sun_gt50",
            "psr_",
            "horizon_",
        ),
    ),
    ("volatiles", ("hydrogen_", "ice_", "coldtrap_")),
    ("resources", ("oxygen_bound", "dist_to_psr", "dist_to_hiti", "dist_to_pit")),
    ("radiation", ("open_sky", "sky_view", "radiation_")),
    ("space_environment", ("magnetic_", "swirl_")),
    ("gravity_geophysics", ("gravity_", "crust_")),
    ("subsurface", ("pit_",)),
    ("operations", ("ops_",)),
    ("communication", ("earth_",)),
]


def group_of(var):
    for g, pre in GROUPS:
        if var.startswith(pre):
            return g
    return "other"


def load_long():
    parts = []
    for f in sorted(OBS_DIR.glob("obs_*.parquet")):
        d = pd.read_parquet(f)
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    for c in LONG_COLS:
        if c not in df.columns:
            df[c] = np.nan if c in ("value", "coverage_fraction", "n_samples") else ""
    df = df[LONG_COLS]
    for c in LONG_COLS:
        if c not in ("value", "coverage_fraction", "n_samples"):
            df[c] = df[c].fillna("").astype(str)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["coverage_fraction"] = pd.to_numeric(df["coverage_fraction"], errors="coerce")
    df["n_samples"] = pd.to_numeric(df["n_samples"], errors="coerce").fillna(0).astype("int64")
    # one record per (region, variable): if duplicated, keep the first (should not happen)
    dup = df.duplicated(["region_id", "variable"], keep="first")
    if dup.any():
        print("WARNING duplicated region/variable records dropped:", int(dup.sum()))
        df = df[~dup]
    df["variable_group"] = df["variable"].map(group_of)
    return df


def load_cov():
    parts = [pd.read_parquet(f) for f in sorted(OBS_DIR.glob("cov_*.parquet"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build():
    regs = load_regions()
    long = load_long()
    long.to_parquet(OUTPUTS / "lunar_observations.parquet", index=False)

    num = long[long.value.notna()]
    wide = num.pivot(index="region_id", columns="variable", values="value")
    txt = long[(long.value.isna()) & (long.value_text != "")].pivot(
        index="region_id", columns="variable", values="value_text"
    )
    # column order by thematic group
    meta_by_var = num.drop_duplicates("variable").set_index("variable")
    order = sorted(
        wide.columns, key=lambda v: ([g for g, _ in GROUPS] + ["other"]).index(group_of(v))
    )
    wide = wide[order]
    ident = regs.set_index("region_id")[
        [
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
        ]
    ]
    # per-group mean coverage (quality/coverage block)
    cov = (
        long[long.value.notna()]
        .groupby(["region_id", "variable_group"])
        .coverage_fraction.mean()
        .unstack()
    )
    cov.columns = [f"qc_mean_coverage_{c}" for c in cov.columns]
    nvar = num.groupby("region_id").variable.nunique().rename("qc_n_variables_available")
    out = ident.join(wide).join(txt).join(cov).join(nvar)
    out.index.name = "region_id"
    out = out.reset_index()
    out["parent_region_id"] = out["parent_region_id"].fillna("")

    # Parquet with schema metadata (per-column provenance)
    table = pa.Table.from_pandas(out, preserve_index=False)
    colmeta = {}
    for v in wide.columns:
        m = meta_by_var.loc[v]
        colmeta[v] = dict(
            unit=m.unit,
            dataset=m.dataset,
            group=group_of(v),
            method=m.processing_method,
            resolution=m.resolution,
            period=m.observation_date,
        )
    fields = []
    for f in table.schema:
        md = colmeta.get(f.name)
        fields.append(f.with_metadata({b"provenance": json.dumps(md).encode()}) if md else f)
    schema = pa.schema(
        fields,
        metadata={
            b"title": b"Lunar regional multidimensional scientific feature table",
            b"crs": CRS_NAME.encode(),
            b"crs_description": CRS_DESCRIPTION.encode(),
            b"region_scheme": b"12 L0 (1/12 sphere each) + 48 L1 (1/48 each), equal-area lat/lon graticule",
            b"long_table": b"lunar_observations.parquet (trace every value: region_id + variable)",
            b"generated_utc": pd.Timestamp.utcnow().isoformat().encode(),
        },
    )
    table = table.cast(schema)
    pq.write_table(table, OUTPUTS / "lunar_region_features.parquet")

    # coverage per region x variable (all combinations)
    allvars = sorted(num.variable.unique())
    grid = pd.MultiIndex.from_product(
        [regs.region_id, allvars], names=["region_id", "variable"]
    ).to_frame(index=False)
    have = num.set_index(["region_id", "variable"])[
        ["coverage_fraction", "resolution", "dataset", "quality", "uncertainty"]
    ]
    g = grid.join(have, on=["region_id", "variable"])
    g["available"] = g["coverage_fraction"].notna()
    # fill dataset/resolution for unavailable combinations from the variable's dataset
    vinfo = num.drop_duplicates("variable").set_index("variable")[
        ["dataset", "resolution", "quality", "uncertainty"]
    ]
    for c in ("dataset", "resolution", "quality", "uncertainty"):
        g[c] = g[c].fillna(g.variable.map(vinfo[c]))
    g["coverage_fraction"] = g["coverage_fraction"].fillna(0.0)
    g = g[
        [
            "region_id",
            "variable",
            "available",
            "coverage_fraction",
            "resolution",
            "dataset",
            "quality",
            "uncertainty",
        ]
    ]
    g.to_csv(OUTPUTS / "region_variable_coverage.csv", index=False, float_format="%.4f")

    reg = by_id()
    rows = []
    for v, d in g.groupby("variable"):
        ds = d.dataset.iloc[0]
        r = reg.get(ds, {})
        rows.append(
            dict(
                variable=v,
                dataset=ds,
                regions_with_data=int(d.available.sum()),
                regions_without_data=int((~d.available).sum()),
                mean_coverage=float(d.coverage_fraction.mean()),
                resolution=d.resolution.iloc[0],
                temporal_coverage=r.get("period", ""),
                unit=vinfo.loc[v].name and meta_by_var.loc[v].unit,
                quality=d.quality.iloc[0],
                group=group_of(v),
            )
        )
    vs = pd.DataFrame(rows).sort_values(["group", "variable"])
    vs.to_csv(OUTPUTS / "variable_summary.csv", index=False, float_format="%.4f")
    print(f"long records: {len(long)}  variables: {len(allvars)}  wide shape: {out.shape}")
    return out, long, g, vs


if __name__ == "__main__":
    build()
