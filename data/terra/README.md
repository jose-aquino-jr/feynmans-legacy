# Dataset da Terra para análogos da Lua e de Marte

Dados terrestres globais: grade de 0,5° com 85.699 pontos de terra, mais 27 sítios nomeados, ou seja,
85.726 locais. A chave é `location_id` (texto `T000001`…), a mesma em todos os arquivos.

## Onde está cada coisa

```text
data/terra/
├── terra.parquet                  # série mensal consolidada usada pelos notebooks
├── tabela_principal.parquet       # cadastro de IDs e coordenadas
├── nichos/                        # Parquets temáticos, dicionários e fontes
│   ├── temperatura/
│   ├── agua_gelo/
│   ├── coordenadas/
│   └── ...                        # demais temas e fontes da Terra
├── spec_analogos/                 # estáticas, de-para do estudo, dicionário e manifesto
└── analise_analogos/              # clusters, previsões, métricas e modelo publicados localmente
```

Os Parquets mensais em `nichos/` mantêm as colunas por tema. Os notebooks leem
`terra.parquet` diretamente, associam os atributos estáticos pelo ID e resolvem
os critérios em `config/`. Os perfis fixos ficam em `data/lua/` e `data/marte/`.

As condições de geração, o controle de qualidade e as limitações estão em
[spec_analogos/README.md](spec_analogos/README.md).

```python
import pandas as pd
principal = pd.read_parquet("data/terra/tabela_principal.parquet")
temp      = pd.read_parquet("data/terra/nichos/temperatura/temperatura_mensal.parquet")
tabela    = principal.merge(temp, on="location_id")
```
