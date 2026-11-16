# Earth dataset for Moon and Mars analogs

The global dataset covers 85,726 Earth sites: 85,699 land points on a 0.5° grid and 27 named sites. All files share the text key `location_id`, such as `T000001`.

```text
data/terra/
├── terra.parquet                  # Consolidated monthly series used by the notebooks
├── tabela_principal.parquet       # Site IDs and coordinates
├── nichos/                        # Thematic Parquet files, dictionaries, and sources
│   ├── temperatura/
│   ├── agua_gelo/
│   ├── coordenadas/
│   └── ...
├── spec_analogos/                 # Static features, site lookup, dictionary, and manifest
└── analise_analogos/              # Clusters, forecasts, metrics, and published model
```

The notebooks read `terra.parquet` directly, join the static features by site ID, and use the comparison criteria in `config/`. The fixed planetary profiles are in `data/lua/` and `data/marte/`.

See the [Earth input specification](spec_analogos/README.md) for how the data was produced, quality checks, and limitations.

```python
import pandas as pd

sites = pd.read_parquet("data/terra/tabela_principal.parquet")
temperature = pd.read_parquet("data/terra/nichos/temperatura/temperatura_mensal.parquet")
table = sites.merge(temperature, on="location_id")
```
