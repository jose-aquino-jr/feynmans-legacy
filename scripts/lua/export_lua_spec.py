"""Export the lunar feature table to the feynmans-legacy notebook contract.

Contract (handoff "Contrato de entrada", lua.parquet): key `base_id`, one row per
lunar base, numeric reference columns only.  Here each of the 60 regions is exported
as a candidate base (`base_id` = region_id); the team decides which rows are "bases".
A sidecar `lua_columns.csv` documents unit, meaning and comparability caveats so that
`nichos.json` pairs are defined with matching physical quantities.

usage: python export_lua_spec.py [--level 1] [--out DIR]
"""

from __future__ import annotations

import argparse

import pandas as pd
from build_lunar_features import group_of
from lunar_common import OUTPUTS

CAVEATS = {
    "elevation": "height above the 1737.4 km lunar sphere; NOT comparable to terrestrial altitude above sea level",
    "tbol": "surface bolometric BRIGHTNESS temperature (K), not air temperature; convert/define proxy before pairing",
    "annual_": "modelled surface kinetic temperature (K)",
    "gravity_": "gravity ANOMALY (mGal) relative to the lunar field model, not total g (lunar g ~1.62 m/s2)",
    "insolation": "W/m2 at the lunar surface without atmosphere",
    "regolith_temp": "relative quantity (K deviation from global mean)",
}


def caveat(v):
    for k, c in CAVEATS.items():
        if v.startswith(k):
            return c
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--level", type=int, default=None, help="export only regions of this level (0 or 1)"
    )
    from lunar_common import ROOT

    repo_default = (
        ROOT.parent / "tratados" / "spec_analogos"
    )  # feynmans-legacy: data/lua -> data/tratados/spec_analogos
    default_out = (
        repo_default
        if ROOT.name == "lua" and ROOT.parent.name == "data"
        else OUTPUTS / "spec_analogos"
    )
    ap.add_argument("--out", default=str(default_out))
    a = ap.parse_args()
    wide = pd.read_parquet(OUTPUTS / "lunar_region_features.parquet")
    long = pd.read_parquet(OUTPUTS / "lunar_observations.parquet")
    if a.level is not None:
        wide = wide[wide.level == a.level]
    ident = {
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
    }
    sci = [
        c
        for c in wide.columns
        if c not in ident and not c.startswith("qc_") and pd.api.types.is_numeric_dtype(wide[c])
    ]
    out = wide[["region_id"] + sci].rename(columns={"region_id": "base_id"})
    out["base_id"] = out["base_id"].astype("string")
    from pathlib import Path

    od = Path(a.out)
    od.mkdir(parents=True, exist_ok=True)
    assert out.base_id.is_unique and out.base_id.notna().all()
    out.to_parquet(od / "lua.parquet", index=False)
    first = long.drop_duplicates("variable").set_index("variable")
    cols = pd.DataFrame(
        [
            dict(
                column=c,
                unit=first.loc[c, "unit"],
                group=group_of(c),
                dataset=first.loc[c, "dataset"],
                meaning=first.loc[c, "processing_method"],
                comparability_caveat=caveat(c),
                n_bases_with_value=int(out[c].notna().sum()),
            )
            for c in sci
        ]
    )
    cols.to_csv(od / "lua_columns.csv", index=False)
    print(f"lua.parquet: {out.shape[0]} bases x {out.shape[1] - 1} numeric columns -> {od}")


if __name__ == "__main__":
    main()
