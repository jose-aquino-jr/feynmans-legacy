# Dados

Catálogo dos conjuntos de dados usados no projeto **Feynman's Legacy**.
O foco deste documento é a base de dados de **Marte**, organizada para
caracterizar locais de pouso e de implantação de uma base permanente.

- **Data do levantamento:** 2026-11-14
- **Fontes permitidas:** apenas NASA — Planetary Data System (PDS),
  NASA Mars Trek, USGS Astrogeology/Astropedia (produtos derivados de
  missões NASA), Data.gov (tag `mars`) e NASA Science.
- **Nenhuma fonte não-NASA foi usada como substituta.** Onde um produto
  NASA não está disponível em formato aberto utilizável, ele é registrado
  em [Limitações](#limitações-e-produtos-não-incluídos).

## Estrutura de `data/`

| Pasta | Conteúdo |
|-------|----------|
| `elevacao/` | Elevação de análogos terrestres (JSON). |
| `macrostrat/` | Estratigrafia dos análogos terrestres (JSON). |
| `open_meteo/`, `power/` | Clima atual e histórico dos análogos (JSON). |
| `osm/`, `usgs_sismos/` | Infraestrutura e sismicidade dos análogos (JSON/GeoJSON). |
| `soilgrids/` | Solos dos análogos (JSON). |
| `external/`, `nasa/` | Reservados para dados externos e NASA diversos. |
| **`marte/`** | **Base de dados de Marte descrita neste documento.** |

### Estrutura de `data/marte/`

```
data/marte/
├── topografia/          # MOLA (DEM global)
├── geologia/            # mapa global 1:15M, SIM 3464 (Jezero/Nili), CRISM
├── ambiente_recursos/   # TES (inércia térmica) e GRS (elementos/neutrons)
├── sites/               # produtos de alta resolução do local de pouso Jezero
└── metadados/           # catálogo e serviços do NASA Mars Trek
```

**Volume total:** ~1,45 GB (247 arquivos, incluindo os dois READMEs).

---

## 1. Topografia e elevação

| Arquivo | Instrumento / missão | Resolução | Fonte | Descrição |
|---------|----------------------|-----------|-------|-----------|
| `marte/topografia/mola_topo_global_1_16deg.tif` | MOLA / Mars Global Surveyor | 1/16° (~3,7 km/pixel), 5760×2880 | [PDS MOLA MEGDR](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg016/) | Topografia mediana global relativa ao areoide GMM3, em metros (int16). GeoTIFF derivado do produto PDS. |
| `marte/topografia/mola_megt90n000eb.img` + `.lbl` | MOLA / Mars Global Surveyor | 1/16° (~3,7 km/pixel) | [PDS MOLA MEGDR](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg016/) | Produto PDS3 original (`MEGT90N000EB.IMG`), inteiro big-endian, com rótulo destacado. |

## 2. Geologia e mineralogia

| Arquivo | Instrumento / missão | Resolução | Fonte | Descrição |
|---------|----------------------|-----------|-------|-----------|
| `marte/geologia/mars_global_geology_15m.gpkg` | USGS — mapa geológico global | 1:15.000.000 (vetor) | [USGS Astropedia](https://astrogeology.usgs.gov/ckan/dataset/a1c6ca2e-c18c-4059-80cc-9a75ae0bf807/resource/16558096-90a2-46c5-8a99-d5aa868a7ec4/download/mars15mgeologicgisrenovation.zip) | Mapa geológico global de Marte em 4 camadas: unidades (2.878), contatos (6.580), estruturas (3.755) e localidades-tipo (77). CRS geográfico, esfera Mars 2000. |
| `marte/geologia/mars_15m_geologic_gis.zip` | USGS — mapa geológico global | 1:15.000.000 | [USGS Astropedia](https://astrogeology.usgs.gov/ckan/dataset/a1c6ca2e-c18c-4059-80cc-9a75ae0bf807/resource/16558096-90a2-46c5-8a99-d5aa868a7ec4/download/mars15mgeologicgisrenovation.zip) | Arquivo-fonte shapefile (mantido para proveniência). |
| `marte/geologia/jezero_nili_geology.gpkg` | USGS SIM 3464 (MRO/CTX, THEMIS, HRSC, HiRISE) | 1:75.000 (vetor) | [USGS SIM 3464](https://pubs.usgs.gov/sim/3464/sim3464_database.zip) | Mapa geológico contínuo de Jezero + Nili Planum em 8 camadas (`GeoUnits_v1`, `GeoContacts`, `SurfaceFeatures`, `LinearFeatures`, `LocationFeatures`, `LandingEllipse`, `Nomenclature`, `MapBoundary`). CRS MTM 77.5°E. |
| `marte/geologia/jezero_sim3464_database.zip` | USGS SIM 3464 | 1:75.000 | [USGS SIM 3464](https://pubs.usgs.gov/sim/3464/sim3464_database.zip) | Pacote-fonte completo (FileGDB + rasters + metadados). |
| `marte/geologia/sim3464/` | USGS SIM 3464 | 1:75.000 + rasters locais | [USGS SIM 3464](https://pubs.usgs.gov/sim/3464/sim3464_database.zip) | Conteúdo extraído: FileGDB `Nili.gdb`, recorte HRSC (`h0988_0000`), hillshade e mosaicos THEMIS dia/noite. |
| `marte/geologia/crism_jezero_hyd_20n073.tif` | CRISM / MRO | ~181 m/pixel, 1537×1636 | [PDS CRISM MRDR](https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-multispectral-v1/mrocr_3201/browse/mc13/) | Produtos de minerais hidratados: SINDEX2, BD2100_2, BD1900_2. |
| `marte/geologia/crism_jezero_fem_20n073.tif` | CRISM / MRO | ~181 m/pixel | idem | Minerais férricos: BD530_2, SH600_2, BDI1000VIS. |
| `marte/geologia/crism_jezero_fm2_20n073.tif` | CRISM / MRO | ~181 m/pixel | idem | Minerais férricos: BD530_2, BD920_2, BDI1000VIS. |
| `marte/geologia/crism_jezero_cr2_20n073.tif` | CRISM / MRO | ~181 m/pixel | idem | Carbonatos: MIN2295_2480, MIN2345_2537, CINDEX2. |
| `marte/geologia/crism_jezero_fal_20n073.tif` | CRISM / MRO | ~181 m/pixel | idem | Alteração ferrosa: R2529, R1506, R1080. |
| `marte/geologia/crism_jezero_chl_20n073.tif` | CRISM / MRO | ~181 m/pixel | idem | Cloretos/zeólitas: ISLOPE1, BD3000, IRR2. |

Os seis produtos CRISM correspondem aos IDs `T1249_MRR{HYD,FEM,FM2,CR2,FAL,CHL}_20N073_0327_4`
e estão acompanhados dos arquivos brutos ENVI/PDS (`.img`, `.hdr`, `.lbl`) com o mesmo nome-base.

## 3. Ambiente e recursos

| Arquivo | Instrumento / missão | Resolução | Fonte | Descrição |
|---------|----------------------|-----------|-------|-----------|
| `marte/ambiente_recursos/tes_ti_day_global.tif` | TES / Mars Global Surveyor | 20 px/° (~2,96 km/pixel), 7200×3600 | [PDS TES TIMAP](https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/mgst_9001.zip) | Inércia térmica diurna global (2007), em J·m⁻²·K⁻¹·s⁻¹ᐟ². |
| `marte/ambiente_recursos/tes_ti_night_global.tif` | TES / Mars Global Surveyor | 20 px/° (~2,96 km/pixel) | idem | Inércia térmica noturna global (2007), mesma unidade. |
| `marte/ambiente_recursos/tes_timap.zip` + `tes_timap/` | TES / Mars Global Surveyor | 20 px/° | idem | Arquivo-fonte e volume PDS extraído (rótulos, máscaras de interpolação, catálogo). |
| `marte/ambiente_recursos/grs_h2o_5deg.tif` | GRS / 2001 Mars Odyssey | Grade de 5° (72×36) | [PDS GRS elementos](https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/) | Água equivalente (H₂O) em % em massa, suavizada (boxcar de 10°). |
| `marte/ambiente_recursos/grs_cl_5deg.tif` | GRS / Odyssey | 5° | idem | Cloro (Cl), % em massa. |
| `marte/ambiente_recursos/grs_fe_5deg.tif` | GRS / Odyssey | 5° | idem | Ferro (Fe), % em massa. |
| `marte/ambiente_recursos/grs_si_5deg.tif` | GRS / Odyssey | 5° | idem | Silício (Si), % em massa. |
| `marte/ambiente_recursos/grs_k_5deg.tif` | GRS / Odyssey | 5° | idem | Potássio (K), % em massa. |
| `marte/ambiente_recursos/grs_th_5deg.tif` | GRS / Odyssey | 5° | idem | Tório (Th), em partes por milhão (ppm). |
| `marte/ambiente_recursos/grs_*_sr_5x5.tab` + `.lbl` | GRS / Odyssey | 5° | idem | Tabelas ASCII originais (concentração, sigma, sigma com CFS). |
| `marte/ambiente_recursos/grs_ns_epithermal.tif` | GRS/NS / Odyssey | 0,5° (720×360) | [PDS GRS special](https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/data/) | Fluxo de nêutrons epitermais (contagens/s), primeiros 25,7 dias de mapeamento. |
| `marte/ambiente_recursos/grs_ns_thermal.tif` | GRS/NS / Odyssey | 0,5° | idem | Fluxo de nêutrons térmicos. |
| `marte/ambiente_recursos/grs_ns_fast.tif` | GRS/NS / Odyssey | 0,5° | idem | Fluxo de nêutrons rápidos. |
| `marte/ambiente_recursos/grs_ns_*_020917.tab` + `.lbl` | GRS/NS / Odyssey | 0,5° | idem | Tabelas ASCII originais (longitude, latitude, fluxo). |

## 4. Produtos compilados do local de pouso — Jezero

| Arquivo | Instrumento / missão | Resolução | Fonte | Descrição |
|---------|----------------------|-----------|-------|-----------|
| `marte/sites/jezero_ctx_ortho_5m.tif` | CTX / MRO (projeto Mars 2020) | 5 m/pixel, 17.766×20.234 | [USGS Planetary Maps](https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXortho_mosaic_5m.tif) | Ortomosaico panromático da cratera Jezero (uint8). |
| `marte/sites/jezero_ctx_dem_20m.tif` | CTX / MRO (projeto Mars 2020) | 20 m/pixel, 4.456×5.067 | [USGS Planetary Maps](https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif) | Modelo digital de elevação da cratera Jezero (float32, metros). |
| `marte/sites/jezero_west_slope_20m.tif` | HiRISE / MRO (DTM derivado) | 20 m/pixel, 2.093×5.235 | [USGS Planetary Maps](https://planetarymaps.usgs.gov/mosaic/mars2020_landing_site_dtm/J03_045994_1986_J03_046060_1986_20m_slope_20m.tif) | Declividade (graus) do delta oeste de Jezero, derivada de par estereoscópico HiRISE. |

## 5. Metadados de serviços (NASA Mars Trek)

| Arquivo | Fonte | Descrição |
|---------|-------|-----------|
| `marte/metadados/mars_trek_config.json` | [NASA Mars Trek](https://trek.nasa.gov/mars/jpl/config/config.json) | Configuração do aplicativo: camadas, serviços, DEM global e endpoints. |
| `marte/metadados/mars_trek_rasters_equirect.json` | [Mars Trek](https://trek.nasa.gov/tiles/Mars/rasters/eq/list.json) | Catálogo de rasters em projeção equirretangular (UUID, título, resolução, endpoint). |
| `marte/metadados/mars_trek_rasters_northpole.json` | [Mars Trek](https://trek.nasa.gov/tiles/Mars/rasters/np/list.json) | Catálogo de rasters em projeção polar norte. |
| `marte/metadados/mars_trek_rasters_southpole.json` | [Mars Trek](https://trek.nasa.gov/tiles/Mars/rasters/sp/list.json) | Catálogo de rasters em projeção polar sul. |
| `marte/metadados/mars_trek_global_dem_imageserver.json` | [Mars Trek](https://trek.nasa.gov/mars/trekarcgis/rest/services/mola128_mola64_merge_90Nto90S_SimpleC_clon0/ImageServer?f=json) | Metadados do serviço de DEM global (`mola128_mola64_merge`, ~463 m). |

---

## Limitações e produtos não incluídos

Os produtos abaixo são NASA e adequados ao objetivo, mas foram **deliberadamente
não baixados** por volume ou por exigirem processamento especializado. Ficam
registrados para trabalhos futuros.

| Produto | Motivo da exclusão |
|---------|--------------------|
| DTM HiRISE em resolução nativa (~1,8 GB por cena) | Volume alto; a declividade de 20 m do delta oeste cobre a necessidade imediata. |
| Mosaico global HRSC–MOLA em 200 m (~11,4 GB) | Volume alto; o MOLA 1/16° (~3,7 km) atende à escala global. |
| DEM MSL/Gale em alta resolução (~3,6 GB) | Fora do foco atual (Jezero); pode ser adicionado se Gale entrar como caso de estudo. |
| Tiles THEMIS de inércia térmica em 100 m (~2,36 GB por tile) | Volume alto; o TES global em ~3 km é a alternativa disponível. |
| Cubos completos CRISM MRDR (~700 MB por cubo) | Volume alto; foram usados os produtos-resumo map-projetados (3 bandas, ~181 m). |
| Dados de radiação MSL/RAD | Disponíveis apenas como contadores brutos por observação (RDR), que exigem calibração e redução para virar taxa de dose; não são uma camada pronta para SIG. |
| Modelo climático marciano (temperatura, pressão, vento) | Não há produto NASA em formato aberto e estático equivalente ao MCD; não foi substituído por fonte não-NASA. |
| Cobertura global de gelo subsuperficial em alta resolução | Existe apenas como mapas derivados de GRS/neutrons em 5°/0,5°, já incluídos. |

### Observações de qualidade

- A topografia MOLA é relativa ao **areoide GMM3**; valores negativos indicam
  elevação abaixo do areoide (ex.: Jezero ≈ −2.645 m; Olympus Mons ≈ +20.046 m).
- A esfera adotada nos produtos globais é a **Mars 2000 (raio 3.396.190 m)**.
  O rótulo PDS do MOLA declara 3.396,0 km (valor arredondado).
- O CRISM tem resolução de ~181 m e cobre a tile `20N073` (5°×5°), suficiente
  para contexto mineralógico regional, não para mapeamento de afloramentos.
- As concentrações GRS em 5° são suavizadas e não resolvem feições locais.
- Os produtos de Jezero têm projeções locais distintas (equirretangular com
  paralelo padrão 18,4663° e MTM 77,5°E); use reprojeção antes de sobrepor.

## Notas técnicas de conversão

- **CRS global padrão:** `+proj=eqc +lat_ts=0 +lon_0=0 +a=3396190 +b=3396190 +units=m`,
  longitudes em **0–360°** (leste positivo). MOLA, TES, GRS e CRISM seguem essa
  convenção; o TES original (−180..180°) foi rotacionado para 0–360°.
- **Formatos:** os produtos PDS3 `IMG` (inteiro big-endian) e as tabelas ASCII
  foram convertidos para GeoTIFF com `rasterio`; os vetores foram convertidos
  para GeoPackage com `pyogrio`.
- **Nodata:** GRS elementos usam `NaN` (origem `9999.999`); CRISM usa `255`;
  DEM e declividade usam `-3,4×10³⁸`.
- **Scripts:** `scripts/convert_marte.py` (rasters) e
  `scripts/convert_marte_vetores.py` (vetores). Execute a partir da raiz:

  ```bash
  python scripts/convert_marte.py
  python scripts/convert_marte_vetores.py
  ```

## Versionamento

Os arquivos em `data/marte/` são pesados e **não devem ser versionados no Git**.
O `.gitignore` ignora `data/marte/**` e mantém apenas os READMEs. Para
reproduzir, baixe das URLs acima (ou use os scripts de conversão após o
download) e mantenha os produtos derivados fora do controle de versão.
