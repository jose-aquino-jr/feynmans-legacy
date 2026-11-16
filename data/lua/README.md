# Regional lunar science dataset

The lunar ETL builds a multidimensional description of 60 lunar regions using open, traceable scientific data from NASA PDS, USGS, JAXA via PDS/USGS, LANL, and GRAIL. Notebooks 01–03 compare lunar and Martian reference sites with Earth. The regional measurements inform the design of those profiles.

- Python scripts and dependencies are under `scripts/lua/`.
- The generated directories are `data/lua/raw/`, `data/lua/processed/`, and `data/lua/outputs/`.
- The scientific export is `data/lua/outputs/lua.parquet` with `lua_columns.csv`.
- The ranking targets are in `data/lua/lua.parquet`. See [reference configuration](../../config/README.md) for mappings and criteria.

## Directory layout

| Directory | Contents |
|---|---|
| `raw/<dataset_id>/` | Original files. `raw/download_manifest.json` records URL, size, Last-Modified, SHA-256, and download date, or a digest for remotely sampled rows. |
| `processed/` | Intermediate arrays (DEM in meters, horizons, remote samples) and `obs/obs_*.parquet` for each dataset. |
| `outputs/` | Final products listed below. |
| `reports/` | Inventory, coverage and gaps, processing report, data dictionary, and validation. |

## Final products

| File | Contents |
|---|---|
| `lunar_regions.geojson` / `.csv` | Hierarchical grid of 12 L0 regions (1/12 of the sphere each) and 48 L1 regions (1/48 each). The polar caps are whole regions (absolute latitude ≥ 73.40° at L1). |
| `lunar_region_features.parquet` | One row per region with about 400 scientific variables. Parquet metadata records provenance by column. |
| `lunar_observations.parquet` | Long-format values with dataset, mission, instrument, product, version, resolution, period, quality, uncertainty, coverage, method, and source. |
| `region_variable_coverage.csv`, `variable_summary.csv` | Coverage by region and variable, and aggregate coverage by variable. |
| `moon_data_inventory.csv` | Inventory tracking cataloging, download, decoding, processing, regionalization, and validation. |
| `qa_flags.csv`, `cross_validation.csv` | Quality flags that retain the underlying data and cross-instrument validation. |

## Reproduce the lunar ETL

From the repository root:

```bash
python -m pip install -r scripts/lua/requirements.txt
cd scripts/lua
python build_lunar_regions.py
python download_lunar_data.py
python process_lunar_data.py
python build_lunar_features.py
python validate_lunar_data.py
python generate_reports.py
python export_lua_spec.py --level 1
```

Omit `--level` to export all 60 regions. Set `LUNAR_DATA_ROOT` to use another data directory. The exporter writes to `outputs/` by default and protects the ranking profile.

## Reference system and comparability

IAU_2015:30100 uses planetocentric latitude, east longitude from 0–360°, a 1,737.4 km LOLA reference sphere, and the Mean-Earth/Polar-Axis frame. Areas are computed on the sphere. GRAIL gravity uses a 1,738 km reference radius. The Wieczorek et al. (2013) crustal models use the principal-axes frame, about 0.02° from the Mean-Earth frame.

`lua_columns.csv` gives the units, meaning, and comparability limits of each column.

- `elevation_*` uses a lunar reference sphere. Earth elevation uses sea level. Relief, slope, and roughness can be compared.
- `tbol_*` is bolometric surface brightness temperature in kelvin.
- `gravity_*` is a gravity anomaly in mGal. Lunar surface gravity is about 1.62 m/s².
- Fields ending in `_p05` through `_p95` can support target intervals if the profile schema adds them.
- Missing data is represented by NaN.

## Acquisition with bandwidth and disk limits

Rasters from 0.2 to 38 GB were sampled systematically from their native data via HTTP Range. The manifest records the sampling intervals and digests. Diviner GCP uses every second longitude column, Diviner PRP every eighth grid row, Kaguya MI one row per 0.5°, LROC WAC TiO2 blocks of 8 rows every 64 rows, and Mini-RF CPR every fourth row. See the [inventory](reports/moon_data_inventory.md) for products that were rejected or only cataloged.
