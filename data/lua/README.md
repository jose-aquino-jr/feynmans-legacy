# Base científica regionalizada da Lua

Etapa **somente Lua** do projeto *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*.
Constrói, a partir de dados científicos abertos e rastreáveis (NASA PDS, USGS, JAXA via PDS/USGS, LANL, GRAIL),
uma assinatura multidimensional de **60 regiões lunares**. A comparação com Terra e Marte acontece nos notebooks
01–03; aqui só se produz a referência lunar e o insumo `lua.parquet` do contrato dos notebooks.

- **Código:** `scripts/lua/` (Python; dependências em `scripts/lua/requirements.txt`)
- **Dados:** `data/lua/` (ignorado no git, exceto este README e `reports/*.md`)
- **Insumo dos notebooks:** `data/tratados/spec_analogos/lua.parquet` + `lua_columns.csv`

## Estrutura de `data/lua/`

| Pasta | Conteúdo |
|---|---|
| `raw/<dataset_id>/` | Arquivos originais, nunca alterados. `raw/download_manifest.json` guarda URL, tamanho, Last-Modified, SHA-256 e data de cada arquivo (ou digest das linhas amostradas remotamente). |
| `processed/` | Arrays intermediários (DEM em metros, horizontes, amostras remotas) e `obs/obs_*.parquet` por dataset. |
| `outputs/` | Produtos finais (tabela abaixo). |
| `reports/` | Inventário, cobertura e lacunas, relatório de processamento, dicionário de dados, validação. |

## Produtos finais (`data/lua/outputs/`)

| Arquivo | Conteúdo |
|---|---|
| `lunar_regions.geojson` / `.csv` | Grade hierárquica: 12 L0 (1/12 da esfera cada) + 48 L1 (1/48 cada). Calotas polares inteiras (\|lat\| ≥ 73,40° em L1). |
| `lunar_region_features.parquet` | Uma linha por região, ~400 variáveis científicas agrupadas por tema; proveniência por coluna nos metadados do Parquet. |
| `lunar_observations.parquet` | Formato longo: cada valor com dataset, missão, instrumento, produto, versão, resolução, período, qualidade, incerteza, cobertura, método e fonte. |
| `region_variable_coverage.csv`, `variable_summary.csv` | Cobertura por região × variável e por variável. |
| `moon_data_inventory.csv` | Inventário com status (catalogued → downloaded → decoded → processed → regionalized → validated). |
| `qa_flags.csv`, `cross_validation.csv` | Sinalizações de qualidade (nunca removem dados) e validação cruzada entre instrumentos. |

## Como reproduzir

```bash
pip install -r scripts/lua/requirements.txt
cd scripts/lua
python build_lunar_regions.py
python download_lunar_data.py
python process_lunar_data.py
python build_lunar_features.py
python validate_lunar_data.py
python generate_reports.py
python export_lua_spec.py --level 1   # sem --level exporta as 60 regiões
```

A pasta de dados pode ser trocada com a variável de ambiente `LUNAR_DATA_ROOT`.

## Referencial

IAU_2015:30100 — latitude planetocêntrica, longitude leste 0–360°, esfera R = 1737,4 km (referência LOLA),
quadro Mean-Earth/Polar-Axis. Nenhum EPSG terrestre é usado. Áreas são esféricas exatas. Exceções registradas:
GRAIL usa raio de referência 1738 km (só gravidade); os modelos de crosta de Wieczorek et al. (2013) estão no quadro
de eixos principais (~0,02° do ME, desprezível na escala regional).

## Uso no `nichos.json` — comparabilidade

`lua_columns.csv` traz unidade, significado e um aviso de comparabilidade por coluna. Pontos críticos:

- `elevation_*` é altura sobre a esfera lunar de 1737,4 km — **não** comparar com altitude terrestre sobre o nível do mar. Relevo, declividade e rugosidade são comparáveis.
- `tbol_*` é **temperatura de brilho** bolométrica da superfície (K), não temperatura do ar.
- `gravity_*` é **anomalia** (mGal), não g total (g lunar ≈ 1,62 m/s²).
- Campos com `_p05`…`_p95` permitem alvos em faixa se o contrato evoluir de alvo pontual para intervalo.
- Ausência de dado é NaN; nunca zero.

## Aquisição sob limite de banda/disco

Rasters de 0,2 a 38 GB foram lidos por **amostragem sistemática de linhas originais** via HTTP Range (valores
nativos, sem miniaturas), com passo e digest registrados no manifesto: Diviner GCP (1 coluna de longitude a cada 2),
Diviner PRP (1 linha da malha a cada 8), Kaguya MI (1 linha a cada 0,5°), LROC WAC TiO2 (blocos de 8 linhas a cada 64),
Mini-RF CPR (1 linha a cada 4). Produtos rejeitados ou só catalogados estão justificados em `reports/moon_data_inventory.md`.
