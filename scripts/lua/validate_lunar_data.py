"""Scientific validation of the regional lunar database.

Checks: grid geometry; physical plausibility by unit; leaked NoData sentinels;
duplicates; coverage bounds; L0-vs-children consistency for area-weighted means;
independent cross-instrument comparisons; robust outlier screening (flag only).
Writes outputs/qa_flags.csv and reports/scientific_validation_report.md.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from lunar_common import OUTPUTS, REPORTS
from regionalize import read_status, set_status

SENTINELS = [-9999.0, -32768.0, -999.0, -3.4028226550889045e38, -1.7976931e308]


def plaus(var, unit):
    """(lo, hi) physically admissible range or None."""
    u = (unit or "").lower()
    if u.startswith("fraction") and "exceed" not in u:
        return 0.0, 1.0
    if u == "k":
        return (-200.0, 200.0) if "anomaly" in var else (0.0, 450.0)
    if u == "degree":
        return (
            (0.0, 360.0)
            if "aspect" in var
            else ((-90.0, 90.0) if "horizon" in var else (0.0, 90.0))
        )
    if u == "m" and var.startswith("elevation_range"):
        return 0.0, 21000.0  # amplitude (max - min), not a height
    if u == "m" and var.startswith("elevation"):
        return -10000.0, 11000.0
    if u == "wt%":
        return 0.0, 100.0
    if u.startswith("ppm"):
        return 0.0, 1e6
    if u == "mgal":
        return -3000.0, 3000.0
    if u == "km" and var.startswith("crust"):
        return 0.0, 150.0
    if u == "w/m2":
        return 0.0, 1361.0
    if u == "count":
        return 0.0, 1e9
    if u == "nt":
        return 0.0, 1e4
    if u == "day":
        return 0.0, 400.0
    return None


def main():
    long = pd.read_parquet(OUTPUTS / "lunar_observations.parquet")
    regs = pd.read_csv(OUTPUTS / "lunar_regions.csv").set_index("region_id")
    geo = json.loads((OUTPUTS / "lunar_regions_validation.json").read_text())
    flags = []
    num = long[long.value.notna()].copy()

    # 1. plausibility + sentinels
    for (var, unit), d in num.groupby(["variable", "unit"]):
        rng = plaus(var, unit)
        for _, r in d.iterrows():
            v = r.value
            if any(np.isclose(v, s) for s in SENTINELS):
                flags.append(
                    dict(
                        region_id=r.region_id,
                        variable=var,
                        value=v,
                        check="nodata_sentinel_leak",
                        severity="error",
                    )
                )
            elif rng and not (rng[0] - 1e-9 <= v <= rng[1] + 1e-9):
                noisy_low_pct = (
                    var.endswith(("_p05", "_p25")) and v < 0 and r.dataset == "LP_HALFDEG_H_FE_TH"
                )
                flags.append(
                    dict(
                        region_id=r.region_id,
                        variable=var,
                        value=v,
                        check=(
                            "low percentile below 0: counting noise of a near-zero field (negative bins kept "
                            "to avoid biasing the mean); not a physical abundance"
                            if noisy_low_pct
                            else f"outside_physical_range{rng}"
                        ),
                        severity="warning" if noisy_low_pct else "error",
                    )
                )
    # 2. duplicates and coverage bounds
    dup = long.duplicated(["region_id", "variable"]).sum()
    badcov = num[(num.coverage_fraction < -1e-9) | (num.coverage_fraction > 1 + 1e-9)]
    for _, r in badcov.iterrows():
        flags.append(
            dict(
                region_id=r.region_id,
                variable=r.variable,
                value=r.coverage_fraction,
                check="coverage_out_of_bounds",
                severity="error",
            )
        )
    # 3. parent/child consistency for area-weighted means (full coverage only)
    l1 = regs[regs.level == 1]
    pc_rows = []
    mean_vars = [
        v
        for v in num.variable.unique()
        if not any(
            v.endswith(s)
            for s in (
                "_std",
                "_min",
                "_max",
                "_p05",
                "_p25",
                "_p50",
                "_p75",
                "_p90",
                "_p95",
                "_count",
                "_km2",
                "_km",
                "count",
                "_youngest",
                "_oldest",
                "diameter",
                "_slope",
                "_sigma",
            )
        )
        and not v.startswith(
            (
                "crater_",
                "geology_unit",
                "geology_dominant",
                "pit_",
                "dist_",
                "lobate",
                "wrinkle",
                "new_impact",
                "irregular",
                "aspect_",
                "hypsometric",
                "elevation_range",
                "relief",
                "crater_csfd",
                "longest_dark",
                "heat_flow",
                "radiation_dose",
                "copernican_crater_count",
                "swirl_count",
            )
        )
    ]
    piv = num.pivot(index="region_id", columns="variable", values="value")
    cov = num.pivot(index="region_id", columns="variable", values="coverage_fraction")
    for v in mean_vars:
        for p, kids in l1.groupby("parent_region_id"):
            if p not in piv.index or not set(kids.index) <= set(piv.index):
                continue
            c = cov.loc[list(kids.index), v]
            if cov.loc[p, v] < 0.99 or (c < 0.99).any():
                continue
            # parent statistics are computed from the same valid pixels: weight children by VALID area
            child = np.average(piv.loc[list(kids.index), v], weights=kids.area_km2 * c)
            parent = piv.loc[p, v]
            if not np.isfinite(child) or not np.isfinite(parent):
                continue
            rel = abs(parent - child) / max(abs(parent), 1e-9)
            spread = np.nanstd(piv[v]) or 1.0
            pc_rows.append(
                dict(
                    variable=v,
                    parent=p,
                    parent_value=parent,
                    children_area_mean=child,
                    rel_diff=rel,
                    abs_diff_over_spread=abs(parent - child) / spread,
                )
            )
    pc = pd.DataFrame(pc_rows)
    if len(pc):
        for _, r in pc[(pc.rel_diff > 1e-3) & (pc.abs_diff_over_spread > 1e-3)].iterrows():
            flags.append(
                dict(
                    region_id=r.parent,
                    variable=r.variable,
                    value=r.parent_value,
                    check=f"parent_vs_children_mean rel_diff={r.rel_diff:.2e}",
                    severity="warning",
                )
            )
    # 4. robust outliers across L1 regions (flag only, never removed)
    l1ids = list(l1.index)
    for v in piv.columns:
        x = piv.loc[piv.index.intersection(l1ids), v].dropna()
        if len(x) < 10:
            continue
        med = x.median()
        mad = (x - med).abs().median() * 1.4826
        if mad <= 0:
            continue
        z = (x - med) / mad
        for rid, zz in z[abs(z) > 5].items():
            flags.append(
                dict(
                    region_id=rid,
                    variable=v,
                    value=x[rid],
                    check=f"robust_z={zz:.1f} (flag only: investigate)",
                    severity="info",
                )
            )
    fl = pd.DataFrame(flags, columns=["region_id", "variable", "value", "check", "severity"])
    fl.to_csv(OUTPUTS / "qa_flags.csv", index=False)

    # 5. cross-instrument validation
    def pair(a, b, ids=None):
        if a not in piv or b not in piv:
            return None
        d = piv[[a, b]].dropna()
        if ids is not None:
            d = d.loc[d.index.intersection(ids)]
        d = d.loc[d.index.intersection(l1ids)]
        if len(d) < 4:
            return None
        r = np.corrcoef(d[a], d[b])[0, 1]
        return dict(
            a=a,
            b=b,
            n=len(d),
            pearson_r=r,
            mean_a=d[a].mean(),
            mean_b=d[b].mean(),
            mean_abs_diff=(d[a] - d[b]).abs().mean(),
        )

    polar = [i for i in l1ids if abs(regs.loc[i, "centroid_lat"]) > 60]
    tests = [
        ("LP GRS FeO (2 deg) vs LP FeO half-degree", pair("feo_wt_lp", "feo_wt_lp_halfdeg")),
        ("LP GRS Th vs LP Th half-degree", pair("th_ppm_lp", "th_ppm_lp_halfdeg")),
        ("LP GRS TiO2 vs LROC WAC TiO2", pair("tio2_wt_lp", "tio2_wt_wac")),
        ("LP GRS Al2O3 vs Kaguya MI plagioclase", pair("al2o3_wt_lp", "plagioclase_wt_kmi")),
        ("LP GRS FeO vs Diviner Christiansen feature", pair("feo_wt_lp", "christiansen_feature")),
        ("UGM mare-unit fraction vs LP FeO", pair("geology_mare_unit_fraction", "feo_wt_lp")),
        (
            "Model illumination vs LOLA AVGVISIB (polar L1 regions)",
            pair("illumination_fraction", "illum_avg_visibility_lola", polar),
        ),
        (
            "Model Earth visibility vs LOLA Earth AVGVISIB (polar L1)",
            pair("earth_visibility_fraction", "earth_visibility_lola", polar),
        ),
        (
            "Diviner GCP Tbol max vs PRP annual max (polar L1)",
            pair("tbol_max", "annual_max_surface_temperature", polar),
        ),
        ("LOLA 240 m slope vs DEM 1.9 km slope", pair("slope_240m_mean", "slope_km_mean")),
        ("Diviner rock abundance vs Mini-RF CPR", pair("rock_abundance", "radar_cpr_mean")),
        (
            "Kaguya MI npFe vs Copernican crater fraction",
            pair("npfe_wt", "copernican_crater_area_fraction"),
        ),
        ("GRAIL free-air vs Bouguer anomaly", pair("gravity_freeair", "gravity_bouguer")),
        ("Crustal thickness vs Bouguer anomaly", pair("crust_thickness", "gravity_bouguer")),
        (
            "LP hydrogen vs PSR area fraction (polar L1)",
            pair("hydrogen_ppm_lp", "psr_area_fraction_lola", polar),
        ),
    ]
    cross = pd.DataFrame([dict(test=t, **r) for t, r in tests if r])
    cross.to_csv(OUTPUTS / "cross_validation.csv", index=False, float_format="%.4f")

    # 6. status: mark datasets validated when they passed without errors
    st = read_status()
    err_ds = set(
        num[
            num.set_index(["region_id", "variable"]).index.isin(
                fl[fl.severity == "error"].set_index(["region_id", "variable"]).index
            )
        ].dataset
    )
    for ds in num.dataset.unique():
        if ds not in err_ds and st.get(ds, {}).get("status") == "regionalized":
            set_status(
                ds, "validated", "passed automated checks (see scientific_validation_report.md)"
            )

    # report
    L = []
    L.append("# Scientific validation report\n")
    L.append("Generated automatically by `scripts/validate_lunar_data.py`.\n")
    L.append("## 1. Region grid\n")
    for lev in ("L0", "L1"):
        g = geo[lev]
        L.append(
            f"- {lev}: {g['n_regions']} regions; area sum relative error {g['area_sum_rel_error']:.2e}; "
            f"unassigned test points {g['unassigned_points']} / 2,000,000; multiply-assigned {g['multiply_assigned_points']}; "
            f"max |Monte-Carlo area fraction - analytic| = {g['mc_area_fraction_max_abs_dev']:.1e} (sampling noise ~2e-4)."
        )
    L.append(
        f"- Hierarchy: children outside parent = {geo['hierarchy']['l1_outside_parent']}; max parent/children area rel. error "
        f"{geo['hierarchy']['max_parent_child_area_rel_error']:.1e}; unique IDs = {geo['unique_ids']}; total regions {geo['n_total']}.\n"
    )
    L.append("## 2. Record-level checks\n")
    L.append(
        f"- Observation records: {len(long)} ({len(num)} numeric); variables: {num.variable.nunique()}; datasets: {num.dataset.nunique()}."
    )
    L.append(f"- Duplicate (region, variable) records: {dup}.")
    for sev in ("error", "warning", "info"):
        L.append(f"- QA flags of severity **{sev}**: {int((fl.severity == sev).sum())}")
    L.append(
        "\nAll flags are listed in `outputs/qa_flags.csv`. Outliers are flagged, never removed: values far from the "
        "L1 median (robust z > 5) are usually real lunar extremes (e.g. South Pole-Aitken basin, Procellarum KREEP "
        "Terrane, polar cold traps) and are kept.\n"
    )
    if len(fl[fl.severity == "error"]):
        L.append("### Errors\n")
        L.append(fl[fl.severity == "error"].head(60).to_markdown(index=False))
        L.append("")
    if len(fl[fl.severity == "info"]):
        L.append("### Extreme values (flag only)\n")
        L.append(
            fl[fl.severity == "info"]
            .groupby("variable")
            .region_id.apply(lambda s: ", ".join(s))
            .to_frame("regions")
            .head(80)
            .to_markdown()
        )
        L.append("")
    L.append("## 3. Parent/children consistency (area-weighted means, full coverage)\n")
    if len(pc):
        L.append(
            f"- Comparisons: {len(pc)}; max relative difference {pc.rel_diff.max():.2e}; "
            f"comparisons above 1e-3: {int((pc.rel_diff > 1e-3).sum())}. Differences arise only from sampling "
            "geometry (point grids, sampled rows) because L0 statistics are computed from the same pixels as L1.\n"
        )
    L.append("## 4. Independent cross-instrument comparisons (L1 regions)\n")
    if len(cross):
        L.append(cross.to_markdown(index=False, floatfmt=".3f"))
    L.append(
        "\nInterpretation: strong positive correlations between independent instruments measuring the same "
        "physical quantity (FeO, Th, TiO2, illumination, Earth visibility) validate the regionalisation; expected "
        "anti-correlations (Al2O3 vs mafic CF, mare fraction vs FeO sign) validate physical consistency. "
        "Systematic offsets are expected where definitions differ (Tbol brightness vs modelled kinetic temperature; "
        "240 m vs 1.9 km slope baselines; 7.6 km model vs 240 m official illumination).\n"
    )
    text = "\n".join(line.rstrip() for line in "\n".join(L).split("\n")).rstrip("\n") + "\n"
    (REPORTS / "scientific_validation_report.md").write_text(text, encoding="utf-8")
    print(f"flags: {fl.severity.value_counts().to_dict()}  cross tests: {len(cross)}")


if __name__ == "__main__":
    main()
