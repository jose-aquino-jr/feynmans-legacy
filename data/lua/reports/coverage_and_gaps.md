# Coverage and gaps

Automated audit per mission category (section 33). `regions_with_data` counts the 60 regions (12 L0 + 48 L1).

| Category | Exists | Global | Partial | Variables | Regions with any data (of 60) | Mean coverage | Uncertainty | Quality | Provenance | Sources / proxies | Gap search notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| topography | yes | yes | no | 57 | 60 | 0.97 | yes | yes | yes | LOLA LDEM/LDSM/LDRM (global) |  |
| geomorphology | yes | yes | no | 16 | 60 | 1.00 | yes | yes | yes | LOLA-derived curvature, TPI, hypsometry; LROC tectonic catalogs | No open global geomorphological-unit map; USGS UGM used as geological proxy. |
| craters | yes | no | yes | 17 | 60 | 0.77 | yes | yes | yes | Robbins 2018 catalog; LROC Copernican/new craters | Depths: Robbins 2018 v1 has NO depth columns (checked); LOLA-based depth catalogs (e.g. Head 2010, D>20 km) not added -> crater depth not_available in this build. |
| boulders | yes | no | yes | 12 | 60 | 0.69 | yes | yes | yes | Diviner rock abundance (global +/-60); Mini-RF CPR | Global boulder counts do not exist in open data (LROC NAC boulder DB v1 Watkins is regional) -> proxy only. |
| geology | yes | no | yes | 23 | 60 | 0.88 | yes | yes | yes | USGS Unified Geologic Map 1:5M; Hiesinger 2011 mare ages |  |
| composition | yes | no | yes | 81 | 60 | 0.95 | yes | yes | yes | LP GRS 2-deg oxides (+errors); LP 0.5-deg Fe/Th; LROC WAC TiO2; Diviner CF | Clementine FeO 1 km on USGS is an RGB visualisation -> rejected. |
| mineralogy | yes | no | yes | 20 | 50 | 0.77 | yes | yes | yes | Kaguya MI plagioclase/olivine/LCP/HCP (+/-50 deg) | M3 strips (no gridded open product located); polar mineralogy unavailable. |
| regolith | yes | no | yes | 15 | 60 | 0.73 | yes | yes | yes | npFe0 maturity (Kaguya MI); Diviner ST thermophysical anomaly; Mini-RF CPR | Regolith thickness: Chang'e MRM maps too large for disk; Apollo soil mechanics are point data; no global thickness map in PDS. |
| temperature | yes | no | yes | 62 | 60 | 0.78 | yes | yes | yes | Diviner GCP Tbol diurnal climatology; Diviner PRP polar annual T; Apollo heat flow (points) | Thermal inertia: Hayne et al. 2017 H-parameter maps not found in PDS; Diviner ST used as proxy. |
| illumination | yes | no | yes | 42 | 60 | 0.77 | yes | yes | yes | LOLA AVGVISIB + LPSR (poles, official); global horizon model (this project) |  |
| water/ice/volatiles | yes | no | yes | 10 | 60 | 0.51 | yes | yes | yes | LP NS hydrogen (global); Diviner PRP ice stability; LOLA PSR; cold-trap fraction | LEND: only EDR/RDR time series archived (no gridded WEH); LAMP GDR not located as files; M3 OH not gridded. |
| resources | yes | yes | no | 39 | 60 | 0.98 | yes | yes | yes | Stoichiometric bound O; LP H; Ti (LP + WAC); distances to PSR / high-Ti | Accessibility is only geometric (distance); no extraction model applied. |
| radiation | yes | no | yes | 7 | 60 | 0.86 | yes | yes | yes | Open-sky solid-angle fraction (terrain shielding); Chang'e-4 LND dose (point) | CRaTER: orbital time series, not spatially resolved -> catalog only. |
| space environment | yes | no | yes | 8 | 60 | 0.25 | yes | yes | yes | LP MAG Level 4 observed crustal field (37 km); LROC swirls | Ravat 2020 surface-field model blocked by a Cloudflare bot challenge (not bypassed). Solar wind/plasma (ARTEMIS, Kaguya PACE) not regionalisable at 60-region scale; LADEE exosphere global only. |
| dust | yes | no | yes | 19 | 60 | 0.77 | yes | yes | yes | Proxies: npFe0 maturity, rock abundance, CPR, Copernican-crater fraction | No direct regional dust-transport observations (LADEE LDEX is orbital/global). |
| gravity/geophysics | yes | yes | no | 21 | 60 | 1.00 | yes | yes | yes | GRAIL GRGM1200A free-air, Bouguer, errors; crustal thickness (4 models); magnetic field |  |
| subsurface | yes | no | yes | 8 | 60 | 0.75 | yes | yes | yes | LROC pit catalog; Mini-RF CPR; GRAIL Bouguer | Lava-tube probability maps not published as open grids; pits are detections, caves unconfirmed. |
| volcanism | yes | no | yes | 9 | 60 | 0.70 | yes | yes | yes | UGM mare units, Dark Mantling (pyroclastic) and dome units; IMPs; Hiesinger mare ages; wrinkle ridges | Pyroclastic deposits taken from UGM Dark Mantling Unit (Gustafson 2012 GIS not openly distributed). |
| landing/mobility | yes | no | yes | 41 | 60 | 0.93 | yes | yes | yes | Slopes (240 m, 1.9 km), roughness, rock abundance, crater density, joint landing criterion |  |
| energy | yes | yes | no | 24 | 60 | 1.00 | yes | yes | yes | Illumination fraction, insolation, longest darkness |  |
| communication | yes | no | yes | 13 | 60 | 0.66 | yes | yes | yes | LOLA Earth visibility (poles); global Earth-visibility model |  |

## Variables with incomplete regional coverage

| variable                                 | dataset                 |   regions_with_data |   regions_without_data |   mean_coverage | resolution                                                                       |
|:-----------------------------------------|:------------------------|--------------------:|-----------------------:|----------------:|:---------------------------------------------------------------------------------|
| radiation_dose_equivalent_surface_insitu | INSITU_POINTS           |                   2 |                     58 |           0.000 | point observation(s) at -45.44, 177.60E                                          |
| heat_flow_insitu                         | INSITU_POINTS           |                   3 |                     57 |           0.000 | point observation(s) at 26.13, 3.63E                                             |
| ice_surface_stable_area_fraction         | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| coldtrap_area_fraction_tmax_lt110K       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature_p95      | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| ice_stability_depth_p50                  | DIVINER_PRP             |                   4 |                     56 |           0.007 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature           | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature_p05       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature_min      | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature_max      | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature          | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature_min       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature_max       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature_p50      | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| ice_stability_depth_mean                 | DIVINER_PRP             |                   4 |                     56 |           0.007 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature_p95       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_max_surface_temperature_p50       | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| ice_stable_area_fraction                 | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| annual_mean_surface_temperature_p05      | DIVINER_PRP             |                   4 |                     56 |           0.019 | ~0.5 km triangles; every 8th mesh row sampled                                    |
| earth_visibility_lola_p50                | LOLA_AVGVISIB_EARTH_65  |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| earth_vis_lola_area_frac_gt50pct         | LOLA_AVGVISIB_EARTH_65  |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| earth_vis_lola_area_frac_never           | LOLA_AVGVISIB_EARTH_65  |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| earth_visibility_lola                    | LOLA_AVGVISIB_EARTH_65  |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| illum_avg_visibility_lola_p95            | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| illum_avg_visibility_lola_p50            | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| illum_avg_visibility_lola                | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| psr_area_fraction_lola                   | LOLA_LPSR_65            |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| illum_lola_area_frac_gt50pct             | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| earth_visibility_lola_p95                | LOLA_AVGVISIB_EARTH_65  |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| illum_avg_visibility_lola_p05            | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| illum_avg_visibility_lola_max            | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| illum_lola_area_frac_lt0p1pct            | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| psr_area_km2_lola                        | LOLA_LPSR_65            |                  26 |                     34 |           0.117 | 240 m/px sampled at 480 m                                                        |
| illum_lola_area_frac_gt80pct             | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| illum_lola_area_frac_gt70pct             | LOLA_AVGVISIB_65        |                  26 |                     34 |           0.117 | 240 m/px, sampled every 2nd line/sample (480 m)                                  |
| mare_model_age_oldest                    | HIESINGER2011_MARE_AGES |                  33 |                     27 |           0.101 | vector                                                                           |
| mare_model_age_mean                      | HIESINGER2011_MARE_AGES |                  33 |                     27 |           0.101 | vector                                                                           |
| mare_model_age_youngest                  | HIESINGER2011_MARE_AGES |                  33 |                     27 |           0.101 | vector                                                                           |
| pit_depth_max                            | LROC_PITS               |                  43 |                     17 |           0.000 | points (~30 m)                                                                   |
| pit_depth_mean                           | LROC_PITS               |                  43 |                     17 |           0.000 | points (~30 m)                                                                   |
| lowca_pyroxene_wt_kmi_p95                | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| highca_pyroxene_wt_kmi_p05               | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| olivine_wt_kmi_std                       | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| olivine_wt_kmi                           | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| olivine_wt_kmi_p50                       | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| lowca_pyroxene_wt_kmi_std                | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| highca_pyroxene_wt_kmi                   | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| olivine_wt_kmi_p95                       | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| plagioclase_wt_kmi_p05                   | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| lowca_pyroxene_wt_kmi_p50                | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| lowca_pyroxene_wt_kmi_p05                | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| olivine_wt_kmi_p05                       | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| plagioclase_wt_kmi_std                   | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| plagioclase_wt_kmi_p95                   | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| plagioclase_wt_kmi_p50                   | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| highca_pyroxene_wt_kmi_p50               | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| highca_pyroxene_wt_kmi_p95               | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| plagioclase_wt_kmi                       | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| lowca_pyroxene_wt_kmi                    | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| highca_pyroxene_wt_kmi_std               | KAGUYA_MI_MINERALS      |                  50 |                     10 |           0.766 | 59 m native; lines sampled every 0.5 deg, 8-pixel (472 m) along-line block means |
| magnetic_field_37km_mean                 | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| magnetic_field_37km_max                  | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| magnetic_field_37km_p95                  | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| magnetic_field_37km_p50                  | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| magnetic_37km_area_frac_gt10nT           | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| magnetic_37km_area_frac_gt2nT            | LP_MAG_L4               |                  55 |                      5 |           0.001 | 0.25 x 0.25 deg bins at 37 km altitude                                           |
| rock_abundance                           | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| tio2_wt_wac_p95                          | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| rock_abundance_p50                       | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| rock_abundance_p95                       | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| rock_abundance_std                       | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| christiansen_feature_p50                 | DIVINER_CF              |                  58 |                      2 |           0.447 | 32 px/deg                                                                        |
| christiansen_feature_p95                 | DIVINER_CF              |                  58 |                      2 |           0.447 | 32 px/deg                                                                        |
| christiansen_feature_std                 | DIVINER_CF              |                  58 |                      2 |           0.447 | 32 px/deg                                                                        |
| tio2_wac_area_frac_ge2wt                 | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| tio2_wac_area_frac_gt6wt                 | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| tio2_wt_wac                              | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| tio2_wt_wac_max                          | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| tio2_wt_wac_p50                          | LROC_WAC_TIO2           |                  58 |                      2 |           0.938 | ~400 m/px; blocks of 8 contiguous lines every 64 lines (1/8 of lines)            |
| christiansen_feature_p05                 | DIVINER_CF              |                  58 |                      2 |           0.447 | 32 px/deg                                                                        |
| christiansen_feature                     | DIVINER_CF              |                  58 |                      2 |           0.447 | 32 px/deg                                                                        |
| rock_abundance_area_frac_gt1pct          | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| rock_abundance_area_frac_gt5pct          | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| rock_abundance_max                       | DIVINER_RA              |                  58 |                      2 |           0.777 | 32 px/deg (~0.95 km)                                                             |
| ops_landing_joint_fraction               | DERIVED_OPERATIONS      |                  58 |                      2 |           0.718 | 16 px/deg (1.9 km) cells; |lat| <= 60 (Diviner RA limit)                         |
| npfe_wt_p05                              | TRANG2020_NPFE          |                  58 |                      2 |           0.856 | 30 px/deg (~1 km)                                                                |
| npfe_wt                                  | TRANG2020_NPFE          |                  58 |                      2 |           0.856 | 30 px/deg (~1 km)                                                                |
| npfe_wt_p95                              | TRANG2020_NPFE          |                  58 |                      2 |           0.856 | 30 px/deg (~1 km)                                                                |
| npfe_wt_p50                              | TRANG2020_NPFE          |                  58 |                      2 |           0.856 | 30 px/deg (~1 km)                                                                |
| regolith_temp_anomaly_night_p50          | DIVINER_ST              |                  58 |                      2 |           0.777 | 32 px/deg                                                                        |
| regolith_temp_anomaly_night_p05          | DIVINER_ST              |                  58 |                      2 |           0.777 | 32 px/deg                                                                        |
| regolith_temp_anomaly_night_std          | DIVINER_ST              |                  58 |                      2 |           0.777 | 32 px/deg                                                                        |
| regolith_temp_anomaly_night_p95          | DIVINER_ST              |                  58 |                      2 |           0.777 | 32 px/deg                                                                        |
| npfe_wt_std                              | TRANG2020_NPFE          |                  58 |                      2 |           0.856 | 30 px/deg (~1 km)                                                                |
| regolith_temp_anomaly_night              | DIVINER_ST              |                  58 |                      2 |           0.777 | 32 px/deg                                                                        |

Regions without data keep **no value** (NaN in the wide table, `available=False` in `region_variable_coverage.csv`). Absence of observation is never encoded as zero or as absence of the phenomenon.

## Items marked not_available_in_open_data (after searching alternatives)

- **Gridded LEND water-equivalent-hydrogen map** — `not_available_in_open_data`: PDS holds LEND EDR/RDR time series only; LP NS H used (global, coarser).
- **Global boulder size-frequency maps** — `not_available_in_open_data`: Only regional NAC boulder catalogs; Diviner rock abundance used as proxy.
- **Global regolith thickness map** — `not_available_in_open_data`: Literature estimates (radar/crater/MRM) not archived as open grids within budget; proxies used.
- **Global thermal inertia / H-parameter grid** — `not_available_in_open_data`: Not found in Diviner PDS bundles; Diviner ST used as proxy.
- **Spatially resolved surface radiation dose** — `not_available_in_open_data`: CRaTER/LND are orbital/point; terrain shielding proxy + Chang'e-4 point value.
- **Lava-tube probability grid** — `not_available_in_open_data`: No open product; pit catalog (detections) + radar/gravity proxies kept separate.
- **Crater depth statistics** — `not_available_in_open_data`: Robbins 2018 v1 has no depth fields; no open global depth catalogue acquired in this build.
