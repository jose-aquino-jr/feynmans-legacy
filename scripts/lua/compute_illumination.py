"""Global topographic illumination, Earth-visibility and sky-view model (this project).

Method (documented in reports/regional_processing_report.md)
-----------------------------------------------------------
1. DEM: LOLA LDEM_16 heights above the 1737.4 km sphere, block-averaged 2x2 to 8 px/deg
   (3.79 km) for horizon ray marching.
2. Horizon: for every 4 px/deg cell centre (1440 x 720), the horizon elevation angle is
   computed in N_AZ azimuths by marching along great circles to 300 km (geometric
   spacing), using exact spherical geometry and lunar curvature:
       angle = atan2((R+h_t) cos(d) - (R+h_o), (R+h_t) sin(d)).
   Because every cell of a latitude row shares the same great-circle offsets, each
   (row, azimuth, distance) step is a fractional shift of one DEM row (exact bilinear).
3. Sun: Cassini-state geometry. In the lunar Mean-Earth frame the Sun's latitude
   oscillates with amplitude 1.543 deg over one eclipse year (346.62 d) and the
   sub-solar longitude decreases 360 deg per synodic month (29.5306 d). One eclipse
   year sampled every 2 h covers the full geometry (amplitude fixed by Cassini laws).
   Solar disc radius 0.2666 deg; visible fraction of the disc above a horizontal
   horizon line uses the circular-segment area formula.
4. Earth: sub-Earth point librates (optical libration) as lon = 7.9 sin(2 pi t/27.5546 d),
   lat = 6.7 sin(2 pi t/27.2122 d); Earth disc radius 0.95 deg.  Approximation documented.
5. Outputs per cell: mean solar disc visibility (= illumination fraction), mean
   horizontal insolation (S0 = 1361 W m-2), mean tracking-panel irradiance, longest
   continuous solar darkness, never-illuminated flag, Earth disc visibility fraction,
   sky-view factor and open-sky solid-angle fraction.
Limitations: 3.8 km DEM cannot resolve sub-km shadows (small PSRs, crater walls);
local surface tilt not applied to insolation (horizontal reference); S0 constant.
"""

from __future__ import annotations

import time

import numpy as np
from lunar_common import PROCESSED

R = 1737.4  # km
N_AZ = 36
DIST = np.geomspace(2.0, 300.0, 44)  # km
RES_DEM = 8
RES_OUT = 4
S0 = 1361.0
SUN_R = 0.2666
EARTH_R = 0.95
DT_H = 2.0


def load_dem8():
    z16 = np.load(PROCESSED / "ldem16_height_m.npy").astype(np.float64) / 1000.0  # km
    z8 = z16.reshape(1440, 2, 2880, 2).mean(axis=(1, 3))
    return z8


def horizons(z8):
    nlat8, nlon8 = z8.shape
    lat_o = 90 - (np.arange(720) + 0.5) / RES_OUT
    lon_o = (np.arange(1440) + 0.5) / RES_OUT
    # observer heights: bilinear sample of z8 at 4ppd centres (= mean of 2x2 block)
    zo = z8.reshape(720, 2, 1440, 2).mean(axis=(1, 3))
    H = np.full((720, 1440, N_AZ), -90.0, dtype=np.float32)
    az = np.radians(np.arange(N_AZ) * 360.0 / N_AZ)
    dd = DIST / R
    t0 = time.time()
    for i, phi_deg in enumerate(lat_o):
        phi = np.radians(phi_deg)
        hmax = np.full((1440, N_AZ), -np.pi / 2)
        for k, a in enumerate(az):
            sphi2 = np.sin(phi) * np.cos(dd) + np.cos(phi) * np.sin(dd) * np.cos(a)
            phi2 = np.arcsin(np.clip(sphi2, -1, 1))
            dlam = np.arctan2(
                np.sin(a) * np.sin(dd) * np.cos(phi), np.cos(dd) - np.sin(phi) * sphi2
            )
            lat2 = np.degrees(phi2)
            # fractional DEM row / column positions
            fr = (90 - lat2) * RES_DEM - 0.5
            fr = np.clip(fr, 0, nlat8 - 1.000001)
            r0 = np.floor(fr).astype(int)
            wr = fr - r0
            # column of target for each observer column j: (lon_o[j] + dlam) * RES_DEM - 0.5
            for s in range(len(dd)):
                row = z8[r0[s]] * (1 - wr[s]) + z8[r0[s] + 1] * wr[s]
                fc = (lon_o + np.degrees(dlam[s])) * RES_DEM - 0.5
                c0 = np.floor(fc).astype(int)
                wc = fc - c0
                ht = row[c0 % nlon8] * (1 - wc) + row[(c0 + 1) % nlon8] * wc
                ang = np.arctan2((R + ht) * np.cos(dd[s]) - (R + zo[i]), (R + ht) * np.sin(dd[s]))
                np.maximum(hmax[:, k], ang, out=hmax[:, k])
        H[i] = np.degrees(hmax).astype(np.float32)
        if i % 60 == 0:
            print(f"  horizon row {i}/720 ({time.time() - t0:.0f}s)", flush=True)
    return H, lat_o, lon_o


def disc_fraction(elev, horizon, radius):
    x = np.clip((elev - horizon) / radius, -1.0, 1.0)
    return 1.0 - (np.arccos(x) - x * np.sqrt(1.0 - x * x)) / np.pi


def body_elev_az(phi, lam, dec, sublon):
    """Elevation and azimuth (deg, az clockwise from north) of a body at (dec, sublon) seen from (phi, lam)."""
    p, d = np.radians(phi), np.radians(dec)
    Hh = np.radians(lam - sublon)
    se = np.sin(p) * np.sin(d) + np.cos(p) * np.cos(d) * np.cos(Hh)
    e = np.degrees(np.arcsin(np.clip(se, -1, 1)))
    az = np.degrees(
        np.arctan2(
            -np.cos(d) * np.sin(Hh), np.cos(p) * np.sin(d) - np.sin(p) * np.cos(d) * np.cos(Hh)
        )
    )
    return e, az % 360


def horizon_at(Hrow, az):
    """Linear interpolation of horizon (n_lon, N_AZ) at azimuth array az (n_lon,)."""
    f = az / (360.0 / N_AZ)
    k0 = np.floor(f).astype(int) % N_AZ
    w = f - np.floor(f)
    idx = np.arange(Hrow.shape[0])
    return Hrow[idx, k0] * (1 - w) + Hrow[idx, (k0 + 1) % N_AZ] * w


def illuminate(H, lat_o, lon_o):
    T_ECL, T_SYN, T_ANO, T_DRA = 346.62, 29.530589, 27.554550, 27.212221
    t = np.arange(0, T_ECL * 24, DT_H) / 24.0  # days
    dec_s = 1.543 * np.sin(2 * np.pi * t / T_ECL)
    sub_s = (-360.0 * t / T_SYN) % 360
    lon_e = 7.9 * np.sin(2 * np.pi * t / T_ANO)
    lat_e = 6.7 * np.sin(2 * np.pi * t / T_DRA)
    nt = len(t)
    out = {
        k: np.zeros((720, 1440), np.float32)
        for k in (
            "sun_vis",
            "insol_h",
            "insol_track",
            "dark_max_h",
            "ever_lit",
            "earth_vis",
            "earth_any",
            "sun_gt50",
        )
    }
    t0 = time.time()
    for i, phi in enumerate(lat_o):
        Hrow = H[i]
        sv = np.zeros(1440)
        ih = np.zeros(1440)
        evis = np.zeros(1440)
        eany = np.zeros(1440)
        g50 = np.zeros(1440)
        run = np.zeros(1440)
        runmax = np.zeros(1440)
        lit_any = np.zeros(1440, bool)
        for n in range(nt):
            e, a = body_elev_az(phi, lon_o, dec_s[n], sub_s[n])
            f = disc_fraction(e, horizon_at(Hrow, a), SUN_R)
            sv += f
            ih += f * np.clip(np.sin(np.radians(e)), 0, None)
            g50 += f > 0.5
            dark = f < 0.01
            run = np.where(dark, run + DT_H, 0.0)
            np.maximum(runmax, run, out=runmax)
            lit_any |= ~dark
            ee, ea = body_elev_az(phi, lon_o, lat_e[n], lon_e[n])
            fe = disc_fraction(ee, horizon_at(Hrow, ea), EARTH_R)
            evis += fe
            eany += fe > 0.0
        # wrap-around darkness run (series is periodic): add leading dark run to trailing one
        # (approximation: recompute leading run length)
        lead = np.zeros(1440)
        still = np.ones(1440, bool)
        for n in range(min(nt, int(400 / DT_H))):  # at most ~16.7 d leading
            e, a = body_elev_az(phi, lon_o, dec_s[n], sub_s[n])
            f = disc_fraction(e, horizon_at(Hrow, a), SUN_R)
            still &= f < 0.01
            lead += still * DT_H
        runmax = np.maximum(runmax, np.where(lead > 0, run + lead, runmax))
        out["sun_vis"][i] = sv / nt
        out["insol_h"][i] = S0 * ih / nt
        out["insol_track"][i] = S0 * sv / nt
        out["dark_max_h"][i] = np.where(lit_any, runmax, np.inf)
        out["ever_lit"][i] = lit_any
        out["earth_vis"][i] = evis / nt
        out["earth_any"][i] = eany / nt
        out["sun_gt50"][i] = g50 / nt
        if i % 60 == 0:
            print(f"  illumination row {i}/720 ({time.time() - t0:.0f}s)", flush=True)
    # sky view factor (horizontal surface, isotropic sky) and open-sky solid-angle fraction
    hpos = np.radians(np.clip(H, 0, 90))
    out["svf"] = np.mean(np.cos(hpos) ** 2, axis=2).astype(np.float32)
    out["sky_solid_frac"] = np.mean(1 - np.sin(hpos), axis=2).astype(np.float32)
    out["horizon_mean"] = np.mean(H, axis=2).astype(np.float32)
    return out


def main():
    z8 = load_dem8()
    hfile = PROCESSED / "horizon_4ppd_36az.npy"
    if hfile.exists():
        H = np.load(hfile)
        lat_o = 90 - (np.arange(720) + 0.5) / RES_OUT
        lon_o = (np.arange(1440) + 0.5) / RES_OUT
    else:
        H, lat_o, lon_o = horizons(z8)
        np.save(hfile, H)
    out = illuminate(H, lat_o, lon_o)
    np.savez_compressed(PROCESSED / "illumination_model_4ppd.npz", lat=lat_o, lon=lon_o, **out)
    print("done")


if __name__ == "__main__":
    main()
