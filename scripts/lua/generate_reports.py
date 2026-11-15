"""Generate inventory (CSV + MD), coverage/gap audit, processing report and data dictionary."""

from __future__ import annotations

import json
import platform
import sys
from importlib import metadata

import pandas as pd
from build_lunar_features import GROUPS, group_of
from dataset_registry import DATASETS
from lunar_common import (
    CRS_DESCRIPTION,
    CRS_NAME,
    LAT_CAP_L0,
    LAT_CAP_L1,
    LAT_MID_L1,
    OUTPUTS,
    REPORTS,
)
from lunar_io import MANIFEST
from regionalize import read_status

# Categories required by the mission and the alternatives searched when a variable is weak/absent.
CATEGORY_AUDIT = [
    ("topography", "topography", "LOLA LDEM/LDSM/LDRM (global)", ""),
    (
        "geomorphology",
        "topography",
        "LOLA-derived curvature, TPI, hypsometry; LROC tectonic catalogs",
        "No open global geomorphological-unit map; USGS UGM used as geological proxy.",
    ),
    (
        "craters",
        "craters_boulders",
        "Robbins 2018 catalog; LROC Copernican/new craters",
        "Depths: Robbins 2018 v1 has NO depth columns (checked); LOLA-based depth catalogs (e.g. Head 2010, D>20 km) not added -> crater depth not_available in this build.",
    ),
    (
        "boulders",
        "craters_boulders",
        "Diviner rock abundance (global +/-60); Mini-RF CPR",
        "Global boulder counts do not exist in open data (LROC NAC boulder DB v1 Watkins is regional) -> proxy only.",
    ),
    ("geology", "geology", "USGS Unified Geologic Map 1:5M; Hiesinger 2011 mare ages", ""),
    (
        "composition",
        "composition",
        "LP GRS 2-deg oxides (+errors); LP 0.5-deg Fe/Th; LROC WAC TiO2; Diviner CF",
        "Clementine FeO 1 km on USGS is an RGB visualisation -> rejected.",
    ),
    (
        "mineralogy",
        "mineralogy",
        "Kaguya MI plagioclase/olivine/LCP/HCP (+/-50 deg)",
        "M3 strips (no gridded open product located); polar mineralogy unavailable.",
    ),
    (
        "regolith",
        "regolith",
        "npFe0 maturity (Kaguya MI); Diviner ST thermophysical anomaly; Mini-RF CPR",
        "Regolith thickness: Chang'e MRM maps too large for disk; Apollo soil mechanics are point data; no global thickness map in PDS.",
    ),
    (
        "temperature",
        "temperature",
        "Diviner GCP Tbol diurnal climatology; Diviner PRP polar annual T; Apollo heat flow (points)",
        "Thermal inertia: Hayne et al. 2017 H-parameter maps not found in PDS; Diviner ST used as proxy.",
    ),
    (
        "illumination",
        "illumination",
        "LOLA AVGVISIB + LPSR (poles, official); global horizon model (this project)",
        "",
    ),
    (
        "water/ice/volatiles",
        "volatiles",
        "LP NS hydrogen (global); Diviner PRP ice stability; LOLA PSR; cold-trap fraction",
        "LEND: only EDR/RDR time series archived (no gridded WEH); LAMP GDR not located as files; M3 OH not gridded.",
    ),
    (
        "resources",
        "resources",
        "Stoichiometric bound O; LP H; Ti (LP + WAC); distances to PSR / high-Ti",
        "Accessibility is only geometric (distance); no extraction model applied.",
    ),
    (
        "radiation",
        "radiation",
        "Open-sky solid-angle fraction (terrain shielding); Chang'e-4 LND dose (point)",
        "CRaTER: orbital time series, not spatially resolved -> catalog only.",
    ),
    (
        "space environment",
        "space_environment",
        "LP MAG Level 4 observed crustal field (37 km); LROC swirls",
        "Ravat 2020 surface-field model blocked by a Cloudflare bot challenge (not bypassed). Solar wind/plasma (ARTEMIS, Kaguya PACE) not regionalisable at 60-region scale; LADEE exosphere global only.",
    ),
    (
        "dust",
        "regolith",
        "Proxies: npFe0 maturity, rock abundance, CPR, Copernican-crater fraction",
        "No direct regional dust-transport observations (LADEE LDEX is orbital/global).",
    ),
    (
        "gravity/geophysics",
        "gravity_geophysics",
        "GRAIL GRGM1200A free-air, Bouguer, errors; crustal thickness (4 models); magnetic field",
        "",
    ),
    (
        "subsurface",
        "subsurface",
        "LROC pit catalog; Mini-RF CPR; GRAIL Bouguer",
        "Lava-tube probability maps not published as open grids; pits are detections, caves unconfirmed.",
    ),
    (
        "volcanism",
        "geology",
        "UGM mare units, Dark Mantling (pyroclastic) and dome units; IMPs; Hiesinger mare ages; wrinkle ridges",
        "Pyroclastic deposits taken from UGM Dark Mantling Unit (Gustafson 2012 GIS not openly distributed).",
    ),
    (
        "landing/mobility",
        "operations",
        "Slopes (240 m, 1.9 km), roughness, rock abundance, crater density, joint landing criterion",
        "",
    ),
    ("energy", "illumination", "Illumination fraction, insolation, longest darkness", ""),
    (
        "communication",
        "communication",
        "LOLA Earth visibility (poles); global Earth-visibility model",
        "",
    ),
]


def _md(lines):
    """Join report lines and strip trailing whitespace (empty metadata fields)."""
    return "\n".join(line.rstrip() for line in "\n".join(lines).split("\n")).rstrip("\n") + "\n"


def pkg_versions():
    out = {}
    for p in (
        "numpy",
        "pandas",
        "pyarrow",
        "scipy",
        "shapely",
        "pyshp",
        "rasterio",
        "requests",
        "pyproj",
        "pyogrio",
    ):
        try:
            out[p] = metadata.version(p)
        except Exception:  # noqa
            out[p] = "n/a"
    return out


def inventory():
    st = read_status()
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    rows = []
    for d in DATASETS:
        ent = [v for k, v in man.items() if v.get("dataset_id") == d["dataset_id"]]
        size = sum(
            e.get("size_bytes", 0) or 0
            for e in ent
            if e.get("mode") in ("full_file", "remote_zip_member")
        )
        remote = sum(e.get("size_bytes", 0) or 0 for e in ent if "sample" in str(e.get("mode")))
        status = st.get(d["dataset_id"], {}).get("status")
        if not status:
            status = {"catalog_only": "catalogued", "rejected": "catalogued (rejected)"}.get(
                d["acquisition"], "catalogued"
            )
            if ent:
                status = "downloaded"
        rows.append(
            dict(
                dataset_id=d["dataset_id"],
                status=status,
                category=d["category"],
                variables=d["variables"],
                mission=d["mission"],
                instrument=d["instrument"],
                product=d["product"],
                version=d["version"],
                identifier=d["identifier"],
                url=" | ".join(d["urls"][:3]) + (" ..." if len(d["urls"]) > 3 else ""),
                documentation=d["documentation"],
                institution=d["institution"],
                period=d["period"],
                resolution=d["resolution"],
                unit=d["unit"],
                crs=d["crs"],
                format=d["format"],
                size_local_bytes=size,
                remote_file_bytes_sampled=remote,
                coverage=d["coverage"],
                quality_uncertainty=d["uncertainty"],
                temporal_class=d["temporal_class"],
                acquisition=d["acquisition"],
                what_it_adds=d["adds"],
                files_in_manifest=len(ent),
                sha256=";".join(
                    sorted(
                        {
                            (
                                e.get("sha256")
                                or e.get("sha256_of_fetched_rows")
                                or e.get("sha256_of_fetched_blocks")
                                or e.get("sha256_of_decoded_sample")
                                or ""
                            )[:16]
                            for e in ent
                        }
                    )
                )[:200],
                license_terms=(
                    "JAXA conditions of use (credit JAXA/SELENE)"
                    if "Kaguya" in d["mission"] or "SELENE" in d["mission"]
                    else "CC0"
                    if d["dataset_id"] in ("USGS_UGM_2020", "RAVAT2020_MAG")
                    else "BSD-3-Clause"
                    if d["dataset_id"] == "GRAIL_CRUST_WIECZOREK2013"
                    else "NASA/PDS open data (cite producers)"
                    if d["acquisition"] != "literature"
                    else "published literature values"
                ),
            )
        )
    inv = pd.DataFrame(rows)
    inv.to_csv(OUTPUTS / "moon_data_inventory.csv", index=False)
    L = [
        "# Moon data inventory\n",
        "Generated by `scripts/generate_reports.py`. Status ladder: catalogued -> downloaded -> decoded -> processed -> "
        "regionalized -> validated. Every acquired file has URL, size, remote Last-Modified and SHA-256 in "
        "`data/raw/download_manifest.json`.\n",
        "Acquisition modes: **full** (file kept unaltered in data/raw), **remote_rows** (systematic subset of original "
        "science lines/records read via HTTP Range: native values, stride documented; used where files are 0.2-38 GB), "
        "**remote_zip_member** (only needed members of an official zip), **catalog_only** / **rejected** (reason given), "
        "**derived** (computed here), **literature** (published in-situ values).\n",
        "## Summary\n",
        inv.groupby("status").dataset_id.count().rename("datasets").to_frame().to_markdown(),
        "\n",
        "## Datasets\n",
    ]
    for r in inv.itertuples():
        L.append(f"### {r.dataset_id} — `{r.status}`\n")
        L.append(f"- **Category / variables:** {r.category} — {r.variables}")
        L.append(
            f"- **Mission / instrument / product:** {r.mission} / {r.instrument} / {r.product}"
        )
        L.append(f"- **Version / identifier:** {r.version} / {r.identifier}")
        L.append(f"- **Institution / period:** {r.institution} / {r.period} ({r.temporal_class})")
        L.append(
            f"- **Resolution / unit / CRS / format:** {r.resolution} / {r.unit} / {r.crs} / {r.format}"
        )
        L.append(f"- **Coverage / uncertainty:** {r.coverage} / {r.quality_uncertainty}")
        L.append(
            f"- **Acquisition:** {r.acquisition}; files in manifest: {r.files_in_manifest}; local bytes {r.size_local_bytes:,}"
            + (
                f"; sampled remote files totalling {r.remote_file_bytes_sampled:,} bytes"
                if r.remote_file_bytes_sampled
                else ""
            )
        )
        L.append(f"- **URL:** {r.url}")
        L.append(f"- **Documentation:** {r.documentation}")
        L.append(f"- **License / terms:** {r.license_terms}")
        L.append(f"- **What it adds:** {r.what_it_adds}\n")
    (REPORTS / "moon_data_inventory.md").write_text(_md(L), encoding="utf-8")
    return inv


def coverage_and_gaps(vs, cov):
    L = [
        "# Coverage and gaps\n",
        "Automated audit per mission category (section 33). `regions_with_data` counts the 60 regions (12 L0 + 48 L1).\n",
        "| Category | Exists | Global | Partial | Variables | Regions with any data (of 60) | Mean coverage | Uncertainty | Quality | Provenance | Sources / proxies | Gap search notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cat, grp, srcs, notes in CATEGORY_AUDIT:
        g = vs[vs.group == grp]
        if cat == "geomorphology":
            g = vs[
                vs.variable.str.startswith(
                    ("curvature", "tpi", "hypsometric", "concave", "convex", "lobate", "wrinkle")
                )
            ]
        if cat == "craters":
            g = vs[
                vs.variable.str.startswith(("crater", "dist_to_crater", "copernican", "new_impact"))
            ]
        if cat == "boulders":
            g = vs[vs.variable.str.startswith(("rock_abundance", "radar_cpr"))]
        if cat == "dust":
            g = vs[
                vs.variable.str.startswith(("npfe", "rock_abundance", "radar_cpr", "copernican"))
            ]
        if cat == "volcanism":
            g = vs[
                vs.variable.str.startswith(
                    (
                        "geology_mare",
                        "geology_pyroclastic",
                        "geology_volcanic",
                        "mare_model_age",
                        "irregular",
                        "wrinkle",
                    )
                )
            ]
        if cat == "landing/mobility":
            g = vs[
                vs.variable.str.startswith(
                    ("slope_", "roughness", "ops_", "rock_abundance", "crater_density")
                )
            ]
        if cat == "energy":
            g = vs[
                vs.variable.str.startswith(("illumination", "insolation", "solar_", "longest_dark"))
            ]
        if cat == "resources":
            g = vs[
                vs.variable.str.startswith(
                    ("oxygen_bound", "hydrogen", "tio2", "dist_to_psr", "dist_to_hiti", "feo_wt_lp")
                )
            ]
        exists = len(g) > 0
        maxreg = int(g.regions_with_data.max()) if exists else 0
        meanc = float(g.mean_coverage.mean()) if exists else 0.0
        has_unc = exists and (
            g.variable.str.contains("sigma|spread").any()
            or cov[cov.variable.isin(g.variable)].uncertainty.astype(str).str.len().gt(0).any()
        )
        L.append(
            f"| {cat} | {'yes' if exists else 'NO'} | {'yes' if maxreg == 60 and meanc > 0.95 else 'no'} | "
            f"{'yes' if exists and meanc < 0.95 else 'no'} | {len(g)} | {maxreg} | {meanc:.2f} | "
            f"{'yes' if has_unc else 'no'} | {'yes' if exists else 'no'} | {'yes' if exists else 'no'} | {srcs} | {notes} |"
        )
    L.append("\n## Variables with incomplete regional coverage\n")
    inc = vs[vs.regions_without_data > 0].sort_values("regions_without_data", ascending=False)
    L.append(
        inc[
            [
                "variable",
                "dataset",
                "regions_with_data",
                "regions_without_data",
                "mean_coverage",
                "resolution",
            ]
        ].to_markdown(index=False, floatfmt=".3f")
    )
    L.append(
        "\nRegions without data keep **no value** (NaN in the wide table, `available=False` in "
        "`region_variable_coverage.csv`). Absence of observation is never encoded as zero or as absence of the phenomenon.\n"
    )
    L.append("## Items marked not_available_in_open_data (after searching alternatives)\n")
    for item, why in (
        (
            "Gridded LEND water-equivalent-hydrogen map",
            "PDS holds LEND EDR/RDR time series only; LP NS H used (global, coarser).",
        ),
        (
            "Global boulder size-frequency maps",
            "Only regional NAC boulder catalogs; Diviner rock abundance used as proxy.",
        ),
        (
            "Global regolith thickness map",
            "Literature estimates (radar/crater/MRM) not archived as open grids within budget; proxies used.",
        ),
        (
            "Global thermal inertia / H-parameter grid",
            "Not found in Diviner PDS bundles; Diviner ST used as proxy.",
        ),
        (
            "Spatially resolved surface radiation dose",
            "CRaTER/LND are orbital/point; terrain shielding proxy + Chang'e-4 point value.",
        ),
        (
            "Lava-tube probability grid",
            "No open product; pit catalog (detections) + radar/gravity proxies kept separate.",
        ),
        (
            "Crater depth statistics",
            "Robbins 2018 v1 has no depth fields; no open global depth catalogue acquired in this build.",
        ),
    ):
        L.append(f"- **{item}** — `not_available_in_open_data`: {why}")
    (REPORTS / "coverage_and_gaps.md").write_text(_md(L), encoding="utf-8")


def processing_report(long):
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    sampled = {k: v for k, v in man.items() if "sample" in str(v.get("mode"))}
    L = [
        "# Regional processing report\n",
        "## Reference frame and coordinates\n",
        f"- CRS: **{CRS_NAME}** — {CRS_DESCRIPTION}.",
        "- Latitude: planetocentric (on the sphere planetographic = planetocentric; WAC TiO2 label says planetographic on a sphere).",
        "- Longitude: east-positive 0-360. Products in -180..180 (Diviner GCP, LP tables, Mini-RF, Kaguya MI, LROC) are converted with lon mod 360.",
        "- Reference surface: sphere R = 1737.4 km (LOLA/IAU). GRAIL maps use reference radius 1738 km (gravity only, recorded). "
        "Ravat magnetic field is evaluated on an ellipsoid (1738.1/1736.0 km) - only the field value is used.",
        "- Polar stereographic products (LOLA illumination/PSR): spherical PS true at the pole, x=(s-S0)*scale, y=(L0-l)*scale, "
        "south lon=atan2(x,y), north lon=atan2(x,-y); true pixel area = scale^2/k^2 with k=2/(1+sin|lat|). "
        "Verified: Shackleton floor (89.66S,129.2E) avg. visibility = 0.000; connecting ridge (89.45S,222.7E) = 0.63.",
        "- No terrestrial EPSG code is applied anywhere. Areas are exact spherical areas, never planar.\n",
        "## Region grid\n",
        f"- 12 L0 regions of 1/12 sphere: two polar caps |lat| >= {LAT_CAP_L0:.4f} deg (sin = 5/6) and 2 x 5 belt sectors of 72 deg longitude.",
        f"- 48 L1 regions of 1/48 sphere: each cap -> inner pole cap |lat| >= {LAT_CAP_L1:.4f} (sin = 23/24) + 3 ring sectors of 120 deg; "
        f"each belt sector -> 2 latitude bands split at {LAT_MID_L1:.4f} deg (sin = 5/12) x 2 longitude halves of 36 deg.",
        "- Justification vs. alternatives (e.g. HEALPix 12/48): identical equal-area hierarchy, but poles are not split into "
        "meridian wedges (PSR/Shackleton region stays one unit) and boundaries follow the native graticule of every PDS map, "
        "so pixel membership is exact and reproducible. Half-open intervals [min,max) with the pole closed; seam at 0/360 is a boundary.",
        "- Area per L1 region: 790,256.8 km2; per L0: 3,161,027.3 km2.\n",
        "## Aggregation method\n",
        "- Each source pixel/sample is assigned to its L1 region; L0 statistics use the same pixels grouped by parent.",
        "- Statistics are area-weighted (exact spherical pixel area). Percentiles are weighted (midpoint CDF interpolation).",
        "- coverage_fraction = spherical area of valid samples / region area. Sampled lines carry stride x line area.",
        "- Categorical geology is kept as text (dominant unit, top-5 units) plus numeric shares.\n",
        "## Systematic remote sampling (bandwidth/disk budget; native values, no thumbnails)\n",
    ]
    rows = []
    for k, v in sampled.items():
        rows.append(
            dict(
                key=k,
                mode=v.get("mode"),
                stride=v.get("row_stride") or v.get("lon_stride") or v.get("mesh_row_stride"),
                remote_size=v.get("size_bytes"),
                digest=(
                    v.get("sha256_of_fetched_rows")
                    or v.get("sha256_of_fetched_blocks")
                    or v.get("sha256_of_decoded_sample")
                    or ""
                )[:16],
            )
        )
    if rows:
        L.append(pd.DataFrame(rows).to_markdown(index=False))
    L.append("\n- Diviner GCP: every 2nd 0.5-deg longitude column (all latitudes and local times).")
    L.append(
        "- Diviner PRP: every 8th mesh row of the 1200x1200 polar mesh; each triangle weighted by its exact 3-D area x 8."
    )
    L.append(
        "- LROC WAC TiO2: every 4th line (1.6 km spacing). Mini-RF CPR: every 4th line. Kaguya MI: every 256th line (0.5 deg) with 8-pixel along-line means."
    )
    L.append("- LOLA polar 240 m products: every 2nd line and sample (480 m).\n")
    L.append("## Per-dataset processing methods\n")
    meth = long.drop_duplicates(["dataset", "processing_method"])[
        ["dataset", "processing_method", "resolution"]
    ]
    for ds, g in meth.groupby("dataset"):
        L.append(f"### {ds}")
        for r in g.itertuples():
            L.append(f"- {r.processing_method} _(resolution: {r.resolution})_")
        L.append("")
    L.append("## Software environment\n")
    L.append(f"- Python {sys.version.split()[0]} on {platform.platform()}")
    for p, v in pkg_versions().items():
        L.append(f"- {p} {v}")
    L.append(f"\n- Processing date (UTC): {pd.Timestamp.utcnow().isoformat(timespec='seconds')}")
    (REPORTS / "regional_processing_report.md").write_text(_md(L), encoding="utf-8")


def data_dictionary(long, wide):
    num = long[long.value.notna() | (long.value_text != "")]
    first = num.drop_duplicates("variable").set_index("variable")
    L = [
        "# Scientific data dictionary — `lunar_region_features.parquet`\n",
        "One row per region (60). Every value is traceable in `lunar_observations.parquet` by (region_id, variable). "
        "Column-level provenance is also stored in the Parquet field metadata (`provenance`).\n",
        "## Identity and geometry columns\n",
        "| Column | Meaning | Unit |",
        "|---|---|---|",
    ]
    for c, m, u in (
        ("region_id", "unique region identifier (L0_xx_CODE / L1_xx_CODE)", "-"),
        ("level", "0 = coarse (12 regions), 1 = fine (48 regions)", "-"),
        ("parent_region_id", "L0 parent of an L1 region (empty for L0)", "-"),
        ("code, name", "short code and descriptive name", "-"),
        ("lat_min, lat_max, lon_min, lon_max", "region bounds (planetocentric, 0-360E)", "degree"),
        ("centroid_lat, centroid_lon", "spherical area centroid", "degree"),
        (
            "area_km2, area_fraction",
            "exact spherical area on R=1737.4 km; fraction of lunar surface",
            "km2, -",
        ),
        ("is_polar_cap, hemisphere_ns, nearside_farside", "geometric descriptors", "-"),
        (
            "qc_mean_coverage_<group>",
            "mean coverage_fraction of that group's variables in the region",
            "fraction",
        ),
        ("qc_n_variables_available", "number of numeric variables with a value", "count"),
    ):
        L.append(f"| {c} | {m} | {u} |")
    for g, _ in GROUPS + [("other", ())]:
        cols = [c for c in wide.columns if c in first.index and group_of(c) == g]
        if not cols:
            continue
        L.append(f"\n## {g}\n")
        L.append(
            "| Column | Meaning / method | Unit | Source (dataset · instrument · product) | Resolution | Limitations |"
        )
        L.append("|---|---|---|---|---|---|")
        for c in cols:
            r = first.loc[c]
            lim = "; ".join(x for x in (str(r.quality), str(r.uncertainty)) if x and x != "nan")
            L.append(
                f"| `{c}` | {r.processing_method} | {r.unit} | {r.dataset} · {r.instrument} · {r.product} | "
                f"{r.resolution} | {lim} |".replace("\n", " ")
            )
    (REPORTS / "scientific_data_dictionary.md").write_text(_md(L), encoding="utf-8")


def main():
    long = pd.read_parquet(OUTPUTS / "lunar_observations.parquet")
    wide = pd.read_parquet(OUTPUTS / "lunar_region_features.parquet")
    vs = pd.read_csv(OUTPUTS / "variable_summary.csv")
    cov = pd.read_csv(OUTPUTS / "region_variable_coverage.csv")
    inventory()
    coverage_and_gaps(vs, cov)
    processing_report(long)
    data_dictionary(long, wide)
    print("reports written")


if __name__ == "__main__":
    main()
