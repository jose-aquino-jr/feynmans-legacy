# Regional processing report

## Reference frame and coordinates

- CRS: **IAU_2015:30100** — Moon 2000 geographic, planetocentric latitude, east-positive longitude 0-360, sphere R=1737.4 km, Mean-Earth/Polar-Axis frame.
- Latitude: planetocentric (on the sphere planetographic = planetocentric; WAC TiO2 label says planetographic on a sphere).
- Longitude: east-positive 0-360. Products in -180..180 (Diviner GCP, LP tables, Mini-RF, Kaguya MI, LROC) are converted with lon mod 360.
- Reference surface: sphere R = 1737.4 km (LOLA/IAU). GRAIL maps use reference radius 1738 km (gravity only, recorded). Ravat magnetic field is evaluated on an ellipsoid (1738.1/1736.0 km) - only the field value is used.
- Polar stereographic products (LOLA illumination/PSR): spherical PS true at the pole, x=(s-S0)*scale, y=(L0-l)*scale, south lon=atan2(x,y), north lon=atan2(x,-y); true pixel area = scale^2/k^2 with k=2/(1+sin|lat|). Verified: Shackleton floor (89.66S,129.2E) avg. visibility = 0.000; connecting ridge (89.45S,222.7E) = 0.63.
- No terrestrial EPSG code is applied anywhere. Areas are exact spherical areas, never planar.

## Region grid

- 12 L0 regions of 1/12 sphere: two polar caps |lat| >= 56.4427 deg (sin = 5/6) and 2 x 5 belt sectors of 72 deg longitude.
- 48 L1 regions of 1/48 sphere: each cap -> inner pole cap |lat| >= 73.4022 (sin = 23/24) + 3 ring sectors of 120 deg; each belt sector -> 2 latitude bands split at 24.6243 deg (sin = 5/12) x 2 longitude halves of 36 deg.
- Justification vs. alternatives (e.g. HEALPix 12/48): identical equal-area hierarchy, but poles are not split into meridian wedges (PSR/Shackleton region stays one unit) and boundaries follow the native graticule of every PDS map, so pixel membership is exact and reproducible. Half-open intervals [min,max) with the pole closed; seam at 0/360 is a boundary.
- Area per L1 region: 790,256.8 km2; per L0: 3,161,027.3 km2.

## Aggregation method

- Each source pixel/sample is assigned to its L1 region; L0 statistics use the same pixels grouped by parent.
- Statistics are area-weighted (exact spherical pixel area). Percentiles are weighted (midpoint CDF interpolation).
- coverage_fraction = spherical area of valid samples / region area. Sampled lines carry stride x line area.
- Categorical geology is kept as text (dominant unit, top-5 units) plus numeric shares.

## Systematic remote sampling (bandwidth/disk budget; native values, no thumbnails)

| key                                                                                 | mode                |   stride |   remote_size | digest           |
|:------------------------------------------------------------------------------------|:--------------------|---------:|--------------:|:-----------------|
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_90s80s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 561c88fc8876beff |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_80s70s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | ddb14a7e1f31c584 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_70s60s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 39b908d35b2dca4a |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_60s50s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | aef8da46773fc404 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_50s40s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | e32f655c3e0832a3 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_40s30s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 3549056763280070 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_30s20s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | b843f06e68091680 |
| KAGUYA_MI_MINERALS:Lunar_Kaguya_MIMap_MineralDeconv_PlagioclasePercent_50N50S.tif   | remote_row_sample   |      256 | nan           | 43ca7e29dd6cd2a0 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_20s10s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | dade3af8ebe56d59 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_10s00s_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | db2f01975cd24458 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_00n10n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | b5701dc1896c18e6 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_10n20n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 5b6842c561b82682 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_20n30n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 30173a3b76aeb184 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_30n40n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | bf5b3428a840d62b |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_40n50n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | e2973b4cfad275bb |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_50n60n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 97f7378bcd8040e3 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_60n70n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | c9617e438f6979d4 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_70n80n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | 65a34f398f2f4608 |
| DIVINER_GCP_TBOL:global_cumul_avg_cyl_80n90n_002.tab                                | remote_block_sample |        2 |   1.56211e+08 | d67894e536d2ef85 |
| DIVINER_PRP:dlre_prp_north.tab                                                      | remote_block_sample |        8 |   6.048e+08   | caef986a9622bead |
| DIVINER_PRP:dlre_prp_south.tab                                                      | remote_block_sample |        8 |   6.048e+08   | a8f8f3d3e7703ba7 |
| KAGUYA_MI_MINERALS:Lunar_Kaguya_MIMap_MineralDeconv_OlivinePercent_50N50S.tif       | remote_row_sample   |      256 | nan           | 37d623d9b65ff940 |
| KAGUYA_MI_MINERALS:Lunar_Kaguya_MIMap_MineralDeconv_OrthopyroxenePercent_50N50S.tif | remote_row_sample   |      256 | nan           | 0292465f33a38f42 |
| MINIRF_CPR_32:global_cpr_32ppd_simp_0c.img                                          | remote_row_sample   |        4 |   2.65421e+08 | 7e268b81b8699071 |
| KAGUYA_MI_MINERALS:Lunar_Kaguya_MIMap_MineralDeconv_ClinopyroxenePercent_50N50S.tif | remote_row_sample   |      256 | nan           | 6ae18062eb201f56 |
| LROC_WAC_TIO2:WAC_TIO2_E350N0450.IMG                                                | remote_row_sample   |        1 |   1.45631e+08 | f7aad52d0f1a165c |
| LROC_WAC_TIO2:WAC_TIO2_E350N1350.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | dc26d91b3425a0ce |
| LROC_WAC_TIO2:WAC_TIO2_E350N2250.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | 2446f0c82608c839 |
| LROC_WAC_TIO2:WAC_TIO2_E350N3150.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | 210556107fefe55f |
| LROC_WAC_TIO2:WAC_TIO2_E350S0450.IMG                                                | remote_row_sample   |        1 |   1.45631e+08 | 39510276ba275dbc |
| LROC_WAC_TIO2:WAC_TIO2_E350S1350.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | 9bfd6ec7c0cc41bb |
| LROC_WAC_TIO2:WAC_TIO2_E350S2250.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | 5a9a7f572517a950 |
| LROC_WAC_TIO2:WAC_TIO2_E350S3150.IMG                                                | remote_row_sample   |        1 |   1.4561e+08  | 12c360a18f3dcdac |

- Diviner GCP: every 2nd 0.5-deg longitude column (all latitudes and local times).
- Diviner PRP: every 8th mesh row of the 1200x1200 polar mesh; each triangle weighted by its exact 3-D area x 8.
- LROC WAC TiO2: every 4th line (1.6 km spacing). Mini-RF CPR: every 4th line. Kaguya MI: every 256th line (0.5 deg) with 8-pixel along-line means.
- LOLA polar 240 m products: every 2nd line and sample (480 m).

## Per-dataset processing methods

### DERIVED_HORIZON_ILLUM
- time-mean visible fraction of solar disc over one eclipse year (2 h steps), horizon from LOLA DEM _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- time-mean S0*f*sin(e) on a horizontal surface, S0=1361 W/m2 _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- time-mean S0*f on a sun-tracking panel (energy potential upper bound, no shadowing by panel height) _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- longest continuous period with <1% of solar disc visible within one eclipse year (cells never lit excluded) _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- area fraction of 7.6 km cells with zero solar disc visibility all year (coarse PSR proxy; lower bound) _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- fraction of time with more than half of the solar disc visible _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- time-mean visible fraction of Earth disc (optical libration model), horizon from LOLA DEM _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- mean over 36 azimuths of cos^2(horizon elevation) for a horizontal surface (radiative sky view) _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- fraction of upper-hemisphere solid angle unobstructed by terrain = relative exposure to isotropic GCR/SPE flux vs flat open ground (geometric shielding proxy) _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_
- mean horizon elevation over 36 azimuths _(resolution: 4 px/deg cells (7.6 km), horizons from 8 px/deg LOLA DEM (3.8 km))_

### DERIVED_OPERATIONS
- area fraction where LOLA 240 m slope < 10 deg AND Diviner rock abundance < 0.01 _(resolution: 16 px/deg (1.9 km) cells; |lat| <= 60 (Diviner RA limit))_
- great-circle distance from each 7.6 km cell centre to nearest LOLA LPSR 240 m PSR pixels (|lat| >= ~55-65 deg mapped domain) _(resolution: from 4 px/deg cell centres)_
- great-circle distance from each 7.6 km cell centre to nearest LROC catalogued pits (Wagner & Robinson) _(resolution: from 4 px/deg cell centres)_
- great-circle distance from each 7.6 km cell centre to nearest LROC WAC TiO2 >= 6 wt% pixels (sampled lines, |lat|<=70) _(resolution: from 4 px/deg cell centres)_

### DIVINER_CF
- area-weighted stats of normalized equatorial-noon Christiansen feature position _(resolution: 32 px/deg)_

### DIVINER_GCP_TBOL
- per 0.5-deg bin: max over local time of Tbol (requires >=1 valid bin 10-14 h); then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: min over night local times 19-5.5 h (>=8 valid night bins); then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: mean over 24 h after periodic linear interpolation (>=50% bins, gaps<=2 h); then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: mean Tbol 11.5-12.5 h local time; then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: mean Tbol 23.5-0.5 h local time; then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: mean Tbol 5.0-5.75 h local time (coldest pre-dawn); then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_
- per 0.5-deg bin: per-bin Tbol max minus night min; then area-weighted regional statistics _(resolution: 0.5 deg x 0.5 deg x 0.25 h; sampled every 2nd longitude column (1 deg))_

### DIVINER_PRP
- area-weighted stats of PRP annual average surface temperature (modelled kinetic temperature) _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_
- area-weighted stats of PRP annual maximum surface temperature (modelled kinetic temperature) _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_
- area fraction with annual max T < 110 K (water-ice surface cold-trap threshold, Paige et al. 2010; Hayne et al. 2015) _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_
- area fraction of triangles with a modelled ice-stability depth (>=0 m) _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_
- area fraction where modelled ice-stability depth <= 1 cm (surface-stable) _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_
- area-weighted ice-stability depth where ice is stable _(resolution: ~0.5 km triangles; every 8th mesh row sampled)_

### DIVINER_RA
- area-weighted stats of Diviner rock abundance (Bandfield et al. 2011) _(resolution: 32 px/deg (~0.95 km))_

### DIVINER_ST
- area-weighted stats of rock-free regolith night temperature deviation from global mean (Bandfield et al. 2011); proxy of fine-regolith thermophysical properties _(resolution: 32 px/deg)_

### GRAIL_CRUST_WIECZOREK2013
- cos(lat)-weighted regional stats of mean crustal thickness of Models 1-4 _(resolution: grid layout: 0.25-deg node grid 721x1441 (principal-axis frame, ~0.02 deg from ME))_
- regional mean of per-cell spread (max-min) among the 4 crustal models _(resolution: grid layout: 0.25-deg node grid 721x1441 (principal-axis frame, ~0.02 deg from ME))_

### GRAIL_GRGM1200A_BOUG
- area-weighted stats of Bouguer gravity anomaly (GRGM1200A, degree 660; crustal density per PDS label) _(resolution: 16 px/deg)_
- area fraction with Bouguer anomaly > +200 mGal (descriptive threshold for strong positive mass anomalies, e.g. mascon centres) _(resolution: 16 px/deg)_

### GRAIL_GRGM1200A_ERR
- area-weighted stats of 1-sigma error of free-air anomaly (propagated from GRGM1200A covariance) _(resolution: 16 px/deg)_

### GRAIL_GRGM1200A_FA
- area-weighted stats of free-air gravity anomaly (GRGM1200A to degree 660, reference radius 1738 km) _(resolution: 16 px/deg map; field expanded to degree 660 (~8 km half-wavelength))_

### HIESINGER2011_MARE_AGES
- area-weighted model age of mapped mare units within region _(resolution: vector)_

### INSITU_POINTS
- site value assigned to the region containing it; NOT representative of the whole region _(resolution: point observation(s) at 26.13, 3.63E)_
- mean of the site values inside the region; NOT representative of the whole region _(resolution: point observation(s) at 26.13, 3.63E; 20.19, 30.77E)_

### KAGUYA_MI_MINERALS
- area-weighted stats of Kaguya MI mineral abundance (Lemelin et al.) _(resolution: 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means)_

### LOLA_AVGVISIB_65
- area-weighted stats of time-averaged visible fraction of the solar disc _(resolution: 240 m/px, sampled every 2nd line/sample (480 m))_
- area fraction of pixels whose average solar visibility exceeds/below threshold _(resolution: 240 m/px, sampled every 2nd line/sample (480 m))_

### LOLA_AVGVISIB_EARTH_65
- area-weighted stats of time-averaged visible fraction of the Earth disc _(resolution: 240 m/px sampled at 480 m)_
- area fraction above/below visibility threshold _(resolution: 240 m/px sampled at 480 m)_

### LOLA_LDEC_4
- area-weighted LOLA shot counts per 4 px/deg cell _(resolution: 4 px/deg (~7.6 km))_

### LOLA_LDEM_16
- area-weighted regional statistics of LDEM_16 heights above R=1737.4 km sphere _(resolution: 16 px/deg (~1.9 km))_
- (mean-min)/(max-min) of LDEM_16 heights _(resolution: 16 px/deg (~1.9 km))_
- slope from centred differences of LDEM_16 on the sphere (|lat|>89 excluded) _(resolution: 1.9 km pixel; centred-difference baseline ~3.8 km)_
- circular mean of downslope azimuth (clockwise from N) for pixels with slope>2 deg; R = mean resultant length (0 = no preferred aspect) _(resolution: 16 px/deg (~1.9 km))_
- Laplacian of LDEM_16 heights (positive = concave/valley, negative = convex/ridge) _(resolution: 16 px/deg (~1.9 km))_
- TPI = height minus 11x11-pixel (~21 km) moving mean; std and depression fraction _(resolution: 16 px/deg (~1.9 km))_

### LOLA_LDRM_16
- area-weighted stats of LOLA RMS residual heights (LDRM_16) _(resolution: 16 px/deg; ~50-150 m along-track scale)_

### LOLA_LDSM_16
- area-weighted stats of LOLA 240 m-baseline bidirectional slope (LDSM_16) _(resolution: 16 px/deg map of 240 m-baseline slopes)_

### LOLA_LPSR_65
- area fraction of LOLA permanently-shadowed pixels _(resolution: 240 m/px sampled at 480 m)_
- sum of PSR pixel areas _(resolution: 240 m/px sampled at 480 m)_

### LP_GRS_ELEM_2DEG
- area-weighted mean of LP GRS MgO weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted mean of LP GRS Al2O3 weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted mean of LP GRS SiO2 weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted mean of LP GRS CaO weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted mean of LP GRS TiO2 weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted mean of LP GRS FeO weight fraction x100 _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted LP GRS K _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted LP GRS Th _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- area-weighted LP GRS U _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- Mg# = 100 Mg/(Mg+Fe) molar, from LP MgO and FeO _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- stoichiometric oxygen bound in the six major oxides (sum w_i * nO*16/M_i); presence/concentration only, not extractable yield _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_
- LP GRS average atomic mass _(resolution: 2-deg equal-area pixels (~60 km); instrument footprint ~150 km FWHM)_

### LP_HALFDEG_H_FE_TH
- area-weighted stats of LP NS epithermal-neutron H (Feldman 2001); top ~1 m; assumes uniform with depth _(resolution: 0.5 deg bins (smoothed; native ~45-60 km))_
- area-weighted stats of LP GRS FeO half-degree (Lawrence 2002) _(resolution: 0.5 deg bins (smoothed; native ~45-60 km))_
- area-weighted stats of LP GRS Th half-degree (Lawrence 2003) _(resolution: 0.5 deg bins (smoothed; native ~45-60 km))_

### LP_MAG_L4
- cos(lat)-weighted regional stats of LP MAG total crustal field |B| at 37 km _(resolution: 0.25 x 0.25 deg bins at 37 km altitude)_
- area fraction of bins with |B| above threshold (descriptive) _(resolution: 0.25 x 0.25 deg bins at 37 km altitude)_

### LROC_COPERNICAN_CRATERS
- polygon area (0.1-deg rasterisation) / region area _(resolution: rasterised at 0.1 deg (~3 km))_
- number of polygons (representative point in region) _(resolution: rasterised at 0.1 deg (~3 km))_

### LROC_IMPS
- number of catalogued features in region _(resolution: points)_

### LROC_LOBATE_SCARPS
- sum of great-circle segment lengths (segment midpoint in region) _(resolution: mapped polylines)_
- length / region area _(resolution: mapped polylines)_

### LROC_NEW_CRATERS
- number of catalogued features in region _(resolution: points)_

### LROC_PITS
- catalogued pits in region _(resolution: points (~30 m))_
- pits with 'Overhangs?' == 'Y' (confirmed overhang) _(resolution: points (~30 m))_
- pits with 'Entrance Ramp?' == 'Y' (unbroken slope to floor) _(resolution: points (~30 m))_
- pits with Terrain containing 'mare' _(resolution: points (~30 m))_
- pits with Terrain containing 'highland' _(resolution: points (~30 m))_
- pits with Terrain containing 'impact melt' _(resolution: points (~30 m))_
- max / mean of catalogued pit depths (shadow measurements) _(resolution: points (~30 m))_

### LROC_SWIRLS
- polygon area (0.1-deg rasterisation) / region area _(resolution: rasterised at 0.1 deg (~3 km))_
- number of polygons (representative point in region) _(resolution: rasterised at 0.1 deg (~3 km))_

### LROC_WAC_TIO2
- area-weighted stats of WAC TiO2 (producer's BDL convention kept: <2 -> 1) _(resolution: ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines))_
- area fraction above threshold (2 wt% = detection limit; 6 wt% = conventional high-Ti mare basalt boundary) _(resolution: ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines))_

### LROC_WRINKLE_RIDGES
- sum of great-circle segment lengths (segment midpoint in region) _(resolution: mapped polylines)_
- length / region area _(resolution: mapped polylines)_

### MINIRF_CPR_32
- area-weighted stats of S-band CPR (SC/OC) _(resolution: 32 px/deg; every 4th line sampled)_
- area fraction with CPR > 1 (very rough or volume-scattering surfaces) _(resolution: 32 px/deg; every 4th line sampled)_

### ROBBINS2018_CRATERS
- count of Robbins craters with D>=2 km (centre in region) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- count of Robbins craters with D>=5 km (centre in region) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- count of Robbins craters with D>=10 km (centre in region) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- count of Robbins craters with D>=20 km (centre in region) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- count of Robbins craters with D>=50 km (centre in region) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- mean D of craters D>=2 km _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- median D of craters D>=2 km _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- largest crater centred in region _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- MLE power-law exponent of cumulative SFD for 2<=D<=100 km (>=30 craters) _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- sum of crater interior areas (D>=2 km) / region area _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- distance from 200k uniform random points to nearest centre of a crater D>=5 km _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_
- distance from 200k uniform random points to nearest centre of a crater D>=20 km _(resolution: crater catalog D>=1 km (completeness ~1-2 km))_

### TRANG2020_NPFE
- area-weighted stats of nanophase Fe0 abundance (space-weathering maturity) _(resolution: 30 px/deg (~1 km))_

### USGS_UGM_2020
- area share of the most extensive map unit _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- number of distinct map units _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- Shannon entropy of unit area shares _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose type contains 'Mare' (mare basalts, incl. mare domes) _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of 'Dark Mantling Unit' (pyroclastic deposits) _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of 'Terra Dome' and 'Mare Dome' units _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of crater-material unit types _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of basin units and named basin formations _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of plains units _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of terra (highland) units _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose FIRST_Un_1 period is pre-Nectarian _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose FIRST_Un_1 period is Nectarian _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose FIRST_Un_1 period is Imbrian _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose FIRST_Un_1 period is Eratosthenian _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- area share of units whose FIRST_Un_1 period is Copernican _(resolution: 1:5,000,000; rasterised at 0.1 deg)_
- map unit symbol(s) by area share (USGS UGM 2020 'FIRST_Unit' style symbol) _(resolution: 1:5,000,000; rasterised at 0.1 deg)_

## Software environment

- Python 3.14.7 on Windows-10-10.0.19045-SP0
- numpy 2.5.4
- pandas 2.3.3
- pyarrow 26.0.1
- scipy 1.18.1
- shapely 2.2.0
- pyshp 3.1.8
- rasterio 1.5.2
- requests 2.34.2
- pyproj 3.8.0
- pyogrio 0.13.0

- Processing date (UTC): 2026-11-15T04:49:09+00:00
