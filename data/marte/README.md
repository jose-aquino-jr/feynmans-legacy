# Marte — anexo técnico

Este diretório contém a base de dados de Marte. O catálogo principal, com
descrição, resolução e links de cada produto, está em
[`../README.md`](../README.md). Este anexo registra a proveniência dos
arquivos brutos e as decisões de conversão.

## Inventário resumido

| Subpasta | Produtos derivados (usar em SIG) | Arquivos brutos mantidos |
|----------|----------------------------------|--------------------------|
| `topografia/` | `mola_topo_global_1_16deg.tif` (1/16°, int16, m) | `mola_megt90n000eb.img` + `.lbl` (PDS3) |
| `geologia/` | `mars_global_geology_15m.gpkg`, `jezero_nili_geology.gpkg`, 6 × `crism_jezero_*_20n073.tif` | `mars_15m_geologic_gis.zip`, `jezero_sim3464_database.zip`, `sim3464/`, 6 × CRISM `.img/.hdr/.lbl` |
| `ambiente_recursos/` | `tes_ti_{day,night}_global.tif`, `grs_{h2o,cl,fe,si,k,th}_5deg.tif`, `grs_ns_{epithermal,thermal,fast}.tif` | `tes_timap.zip`, `tes_timap/`, `.tab`/`.lbl` de GRS |
| `sites/` | `jezero_ctx_ortho_5m.tif`, `jezero_ctx_dem_20m.tif`, `jezero_west_slope_20m.tif` | — |
| `metadados/` | 5 JSON do NASA Mars Trek | — |

## Proveniência

Todos os arquivos vêm de servidores NASA/USGS e foram baixados em 2026-11-14.

| Grupo | URL de origem |
|-------|---------------|
| MOLA MEGDR 1/16° | https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg016/ |
| TES thermal inertia | https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001.zip |
| GRS elementos (5°) | https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/ |
| GRS nêutrons (0,5°) | https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/ |
| CRISM MRDR browse (`mc13`) | https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-multispectral-v1/mrocr_3201/browse/mc13/ |
| Mapa geológico global 1:15M | https://astrogeology.usgs.gov/ckan/dataset/a1c6ca2e-c18c-4059-80cc-9a75ae0bf807/resource/16558096-90a2-46c5-8a99-d5aa868a7ec4/download/mars15mgeologicgisrenovation.zip |
| SIM 3464 (Jezero/Nili) | https://pubs.usgs.gov/sim/3464/sim3464_database.zip |
| Jezero CTX ortomosaico 5 m | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXortho_mosaic_5m.tif |
| Jezero CTX DEM 20 m | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif |
| Declividade oeste de Jezero 20 m | https://planetarymaps.usgs.gov/mosaic/mars2020_landing_site_dtm/J03_045994_1986_J03_046060_1986_20m_slope_20m.tif |
| NASA Mars Trek (config/catálogo) | https://trek.nasa.gov/mars/jpl/config/config.json e https://trek.nasa.gov/tiles/Mars/rasters/eq/list.json |

## Conversões

- `scripts/convert_marte.py`
  - MOLA: lê `>i2` cru 2880×5760 e grava GeoTIFF com CRS equirretangular.
  - TES: lê `>i2` 3600×7200, rotaciona de −180..180° para 0..360° e grava.
  - CRISM: copia ENVI `.img` (uint8, 3 bandas) preservando CRS/transform.
  - GRS: tabelas ASCII → grades 72×36 (5°) e 720×360 (0,5°).
- `scripts/convert_marte_vetores.py`
  - Shapefiles 1:15M → `mars_global_geology_15m.gpkg`.
  - Camadas do FileGDB `Nili.gdb` → `jezero_nili_geology.gpkg`.

## Limitações

Ver a seção [Limitações e produtos não incluídos](../README.md#limitações-e-produtos-não-incluídos)
no catálogo principal. Em resumo: não foram baixados HiRISE DTM nativo,
HRSC–MOLA 200 m global, DEM de Gale, tiles THEMIS de 100 m, cubos CRISM
completos nem dados de radiação MSL/RAD prontos para uso.
