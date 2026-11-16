# Support facilities

`nasa_bases_suporte.parquet` is a 182-row GeoParquet file covering NASA, partner, contractor, and campaign support facilities. It includes field centers, DSN/NSN/TDRS networks, launch sites, balloon bases, and logistics support.

| Column | Use |
|---|---|
| `id`, `nome`, `categoria`, `operador`, `pais` | Identification and display. |
| `lat`, `lon` | Distance to Earth sites. |
| `prioridade_combinada` (0–1) | Facility weight in the support score and routes. |
| `vinculo` | Facilities with the value `Restrita` are excluded. |
| `continente` | Locations with the value `Oceano` (splashdown zones) are excluded. |

The file cites public sources including NASA, ESA ESTRACK, JAXA, ILRS/IVS, and Wikipedia. Its reference date is 2026-11-15. The `coord_precisao` column flags approximate positions, such as city centers or centroids.

`src/feynmans_legacy/logistics.py` uses this dataset. The pipeline publishes it as `data/tratados/analogos/apoios.parquet` without WKB geometry.
