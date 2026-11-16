# Mars data technical appendix

This directory contains Mars source data and derived products. The [main catalog](catalogo.md) lists the description, resolution, and download links for each product. This appendix records source provenance and conversion details.

## Inventory

| Directory | Derived products for GIS | Retained source files |
|---|---|---|
| `topografia/` | `mola_topo_global_1_16deg.tif` (1/16°, int16, meters) | `mola_megt90n000eb.img` and `.lbl` (PDS3) |
| `geologia/` | `mars_global_geology_15m.gpkg`, `jezero_nili_geology.gpkg`, and six `crism_jezero_*_20n073.tif` files | `mars_15m_geologic_gis.zip`, `jezero_sim3464_database.zip`, `sim3464/`, and six CRISM sets with `.img/.hdr/.lbl` |
| `ambiente_recursos/` | `tes_ti_{day,night}_global.tif`, `grs_{h2o,cl,fe,si,k,th}_5deg.tif`, and `grs_ns_{epithermal,thermal,fast}.tif` | `tes_timap.zip`, `tes_timap/`, and GRS `.tab` and `.lbl` files |
| `sites/` | `jezero_ctx_ortho_5m.tif`, `jezero_ctx_dem_20m.tif`, and `jezero_west_slope_20m.tif` | — |
| `metadados/` | Five NASA Mars Trek JSON files | — |

## Provenance

The source files were downloaded from NASA and USGS servers on 2026-11-14.

| Group | Source URL |
|---|---|
| MOLA MEGDR 1/16° | https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg016/ |
| TES thermal inertia | https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001.zip |
| GRS elements (5°) | https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/ |
| GRS neutrons (0.5°) | https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/ |
| CRISM MRDR browse (`mc13`) | https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-multispectral-v1/mrocr_3201/browse/mc13/ |
| Global 1:15M geology map | https://astrogeology.usgs.gov/ckan/dataset/a1c6ca2e-c18c-4059-80cc-9a75ae0bf807/resource/16558096-90a2-46c5-8a99-d5aa868a7ec4/download/mars15mgeologicgisrenovation.zip |
| SIM 3464 (Jezero/Nili) | https://pubs.usgs.gov/sim/3464/sim3464_database.zip |
| Jezero CTX orthomosaic, 5 m | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXortho_mosaic_5m.tif |
| Jezero CTX DEM, 20 m | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif |
| Western Jezero slope, 20 m | https://planetarymaps.usgs.gov/mosaic/mars2020_landing_site_dtm/J03_045994_1986_J03_046060_1986_20m_slope_20m.tif |
| NASA Mars Trek configuration and catalog | https://trek.nasa.gov/mars/jpl/config/config.json and https://trek.nasa.gov/tiles/Mars/rasters/eq/list.json |

## Conversions

- `scripts/convert_marte.py` reads the raw 2880 × 5760 MOLA big-endian int16 raster and writes a GeoTIFF with an equirectangular CRS. It rotates the 3600 × 7200 TES raster from −180–180° to 0–360°, copies three-band CRISM ENVI images while preserving their CRS and transform, and converts GRS ASCII tables into 72 × 36 (5°) and 720 × 360 (0.5°) grids.
- `scripts/convert_marte_vetores.py` converts the 1:15M shapefiles to `mars_global_geology_15m.gpkg` and the `Nili.gdb` layers to `jezero_nili_geology.gpkg`.

## Limitations

See the [limitations in the main catalog](catalogo.md#limitações-e-produtos-não-incluídos). The collection excludes the native HiRISE DTM, global 200 m HRSC–MOLA, a Gale DEM, 100 m THEMIS tiles, complete CRISM cubes, and ready-to-use MSL/RAD radiation data.
