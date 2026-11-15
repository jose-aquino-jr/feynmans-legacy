# Dataset da Terra para análogos da Lua e de Marte

Dados terrestres globais: grade de 0,5° com 85.699 pontos de terra, mais 27 sítios nomeados, ou seja,
85.726 locais. A chave é `location_id` (texto `T000001`…), a mesma em todos os arquivos.

## Onde está cada coisa

```
data/
├── tabela_principal.parquet          location_id → coordenadas ("lat,lon")
├── coordenadas/                      lat/lon, id_ponto, IDs por precisão id_n0…id_n4, país, região
├── temperatura/                      ┐
├── iluminacao_radiacao/              │ cada pasta de tema tem:
├── relevo/                           │   <tema>.parquet              resumo por local (média/mín/máx dos 12 meses recentes ou valor fixo)
├── agua_gelo/                        │   <tema>_mensal.parquet       série mensal 201901–202608 (location_id, anomes), quando o tema varia no tempo
├── poeira_vento_processos/           │   <tema>_padronizado.parquet  pronto para k-means (log1p onde indicado, mediana nos faltantes, z-score)
├── geologia_superficie/              │   dicionario_<tema>.csv       unidade, fonte, descrição e faixa de cada coluna
├── biologia/                         │
├── subsuperficie/                    │
├── operacoes/                        ┘
├── dicionario/                       dicionário completo, grupos de colunas e escalas da padronização
└── tratados/spec_analogos/           insumos no contrato dos notebooks 01 → 02 → 03 (não mexer no formato)
```

- Os arquivos `*_mensal.parquet` são o `terra.parquet` do contrato separado por tema. O conteúdo é o mesmo.
- Os notebooks leem **só** `data/tratados/spec_analogos/`. As pastas por tema servem para análise, clustering e o app.
- A geração, o controle de qualidade, as fontes (NASA GIBS: MERRA-2 e MODIS; SEDAC; SRTM/ETOPO; SoilGrids; Macrostrat;
  EONET) e as limitações estão descritos em `tratados/spec_analogos/README.md`.

```python
import pandas as pd
principal = pd.read_parquet("data/tabela_principal.parquet")
temp      = pd.read_parquet("data/temperatura/temperatura_mensal.parquet")
tabela    = principal.merge(temp, on="location_id")
```
