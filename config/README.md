# Comparison profiles and reference targets

The notebooks read monthly observations from `data/terra/terra.parquet`, keyed by `location_id` and `anomes`, and join the static features in `data/terra/spec_analogos/estaticas.parquet` by site ID. The thematic Parquet files in `data/terra/nichos/` support exploration and ETL. Comparison profiles select columns from the consolidated table and can share variables.

| File | Purpose |
|---|---|
| `nichos.json` | Maps each body and comparison profile to Earth variables, reference columns, tolerances, and weights. |
| `criterios_referencia_proposta.csv` | Records each base's target, derivation rule, and criterion parameters. |
| `../data/lua/lua.parquet` | Ranking profiles for two lunar bases. |
| `../data/marte/marte.parquet` | Ranking profiles for six Martian bases. |
| `../data/lua/outputs/lua.parquet` | Scientific export by lunar region, with `lua_columns.csv`. |

Notebook 01 checks that the Earth columns are numeric and that the dictionary, catalog, reference profiles, and JSON agree. Each score uses the absolute distance from the target divided by the tolerance, in the units of the corresponding Earth measurement.

For scientific comparisons, document the physical quantity, source unit, conversion, spatial scale, aggregation period, and rationale for any proxy. Converting Kelvin to Celsius aligns the units of surface brightness temperature and air temperature at 2 m, which measure different quantities. Align resolution and method when comparing relief or slope, and define a common basis when comparing elevations measured against different planetary reference surfaces.

To add a profile, consult the scientific dictionary, select the bases, document each comparison, and update the profile Parquet, `nichos.json`, and the CSV catalog together. Then run Notebooks 01, 02, and 03 in order.

## Measured Moon and Mars values

`valores_reais.csv` records the value, unit, physical quantity, confidence (`alta`, `media`, `baixa`), and source for each base and variable. Running `python scripts/aplicar_valores_reais.py` writes those targets to the lunar and Martian profile files and updates the catalog, retaining the previous target in `alvo_proxy`.

Some measured targets lie beyond Earth's range, such as Martian pressure near 0.7 kPa and lunar pressure near zero. Their base-specific tolerance (`<variable>__tolerancia` in Parquet) is the greater of the distances from the target to Earth's 1st and 99th percentiles. The score uses `100 × (1 − |value − target| / tolerance)`, with negative scores clipped to zero. When there is no base-specific tolerance, the configuration in `nichos.json` applies.

| Target type | When it applies | Examples |
|---|---|---|
| Measured | A physical measurement or calculation has a source. | Pressure, temperature, radiation, solar elevation, NDVI, rainfall, organic carbon, wind, and Phoenix pH. |
| Classification | Site geology defines presence or absence. | Lithology, permafrost, lava tubes, bare soil, flat terrain, and albedo. |
| Earth equivalent | Comparable measurements at the same scale are unavailable. | Relief, slope, topographic position, elevation (MOLA/LOLA and sea level use different reference surfaces), airborne dust in µg/m³, and lunar polar temperature and amplitude. |

After applying measured targets, run `make analogos` to regenerate the pairs.
