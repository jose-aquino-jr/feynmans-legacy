# Earth inputs for Notebooks 01–03

This directory contains the Earth inputs used by `src/feynmans_legacy/analog_study.py` and the three study notebooks.

| File | Key | Contents |
|---|---|---|
| `data/terra/terra.parquet` | `location_id, anomes` | 85,726 sites × 92 months (201901–202608), or 7,886,792 rows, with 16 monthly variables. |
| `estaticas.parquet` | `location_id` | 67 static attributes covering relief, lithology, soil, elevation-adjusted pressure, solar geometry, land cover, events, and permafrost. |
| `coordenadas.parquet` | `location_id` | WGS84 latitude and longitude in decimal degrees (float64). |
| `data/lua/lua.parquet` | `base_id` | Two proposed profiles: `LUA_POLO_SUL` and `LUA_MARE_TUBOS`. |
| `data/marte/marte.parquet` | `base_id` | Six proposed profiles: `MARTE_JEZERO`, `MARTE_GALE`, `MARTE_MERIDIANI`, `MARTE_GELO_MEDIAS_LAT`, `MARTE_THARSIS_TUBOS`, and `MARTE_MEDUSAE_YARDANGS`. |
| `config/nichos.json` | Body → profile → variable | Nine Moon profiles and 12 Mars profiles covering 34 distinct variables. |

Notebook 01 validates `dicionario_spec.csv` and `config/criterios_referencia_proposta.csv`. The files `cobertura_terra_por_mes.csv` and `manifesto.json` record monthly coverage and publication metadata.

## Keys and site IDs

- Read `location_id` as text to preserve leading zeroes. It consists of `T` and six digits, from `T000001` to `T085726`.
- IDs through `T085699` are exact centers of the 0.5° land grid. IDs from `T085700` through `T085726` are the 27 named project sites at their actual coordinates. Names and countries are in `data/terra/nichos/coordenadas/coordenadas.parquet`.
- `anomes` is an int32 YYYYMM value. The monthly Parquet is sorted by `location_id` and then `anomes`.

## Monthly values and quality checks

- Monthly NASA GIBS products (MERRA-2 and MODIS Terra) were decoded using each layer's official color map. Each site value is the median of the 0.25° pixels within its centered 0.5° window.
- Values are rounded to the color map precision. The dictionary's `descricao` column lists limits. Values at a limit represent an inequality, such as air temperature ≤ −53 °C or airborne dust ≥ 90 µg/m³.
- Unpublished months remain missing: MERRA-2 temperature for 202312, 202401, and 202405, and NDVI for 202504. Day–night LST amplitude is the difference between daytime and nighttime LST in the same month.
- The layer audit matched 100% of valid pixels to the published color maps. Exclusions included CERES because its WMS palette differs, MERRA-2 pressure because it saturates at ≤800 and ≥1020 hPa, MERRA-2 skin temperature because it saturates at ≤ −33 °C, and MODIS snow cover because 0% and missing observations were indistinguishable. Elevation-derived standard-atmosphere pressure is used in place of the excluded pressure layer.
- Cross-checks against NASA POWER at the 27 named sites found a temperature correlation of 0.999 with mean error of 0.8 °C, and precipitation and wind correlations of 0.93–0.96.

## Recorded validation results

- **Notebook 01:** No missing or duplicate keys, complete coordinate coverage, no repeated columns between monthly and static datasets, and all 34 profile variables present. In 202608, 22 variables were selected for k-means with three clusters. Radiation, NDVI, albedo, soil carbon, population, soil moisture, and pH had about 70% coverage because the source layers do not cover the Antarctic and Greenland ice sheets. The 80% threshold applies to clustering. Ranking uses its own coverage rule.
- **Notebook 02:** LightGBM trains by dynamic variable and horizon on a 400-site sample. Optuna tunes one configuration per variable over two validation months. MAE is compared against default LightGBM and persistence. The final three months are held out for testing. Metrics and tuning details are in `metricas_previsao.parquet` and `otimizacao_lightgbm.json`. Batch inference writes horizons 1–3 to `previsoes.parquet` for all sites with enough history.
- **Notebook 03:** Profile resolution and ranking ran for all eight bases using the combined profile (`Todos`) and an individual profile. Examples from that validation run are listed below.

| Base | First-ranked site using the combined profile |
|---|---|
| `LUA_POLO_SUL` | Canadian Arctic (Baffin Island) |
| `LUA_MARE_TUBOS` | Basalt terrains in the Algerian Sahara and Arabia |
| `MARTE_JEZERO` | Nubian Desert, Sudan |
| `MARTE_GALE` | Mojave Desert, USA |
| `MARTE_MERIDIANI` | Tarim Basin, China |
| `MARTE_GELO_MEDIAS_LAT` | Ice-free northern Greenland coast and Canadian Arctic |
| `MARTE_THARSIS_TUBOS` | Andean Puna and Altiplano |
| `MARTE_MEDUSAE_YARDANGS` | Lut Desert, Iran |

## Reference profiles and regeneration

See the [reference configuration](../../../config/README.md) for the current targets and tolerances. In the initial profiles, targets were fixed values or Earth percentiles used as proxies for conditions beyond Earth's range. The initial tolerance was the Earth 95th minus the 5th percentile, or 1 for binary variables, with equal weights. The CSV catalog records each derivation.

These commands were used by the upstream Earth dataset tooling. They require that tooling and its source inputs separately from this checkout. To run the application with the published inputs, follow the [main README](../../../README.md).

```bash
python construir_dataset_terra.py
python exportar_spec_analogos.py --inicio 201901 --fim 202608
python validar_spec_analogos.py --repo /path/to/feynmans-legacy
```

The first command produces `data/dataset_ml` (about two hours initially, or four minutes with cache). The export takes about nine minutes with cache. If it writes the old directory layout, distribute the files according to the table above before validating. Coordinate with the team before publishing replacement Parquets or large artifacts.
