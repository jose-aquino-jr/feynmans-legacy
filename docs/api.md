# API — Feynman's Legacy

API HTTP **somente leitura** em FastAPI/Pydantic v2 para consumo pelo Front-End.
A fonte de dados é exclusivamente:

- `data/tratados/`: datasets em **CSV** e **Parquet**.
- `models/`: artefatos de modelo (apenas metadados; nada é carregado/executado).

> Não há endpoints de escrita, autenticação implementada nem front-end neste
> repositório. O ponto de extensão de autenticação é
> `app.dependencies.get_current_principal`.

## Execução

```bash
cp .env.example .env          # no Windows: copy .env.example .env
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install -e .
uvicorn app.main:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Base da API: `http://127.0.0.1:8000/api/v1`

Nos exemplos abaixo, defina a base:

```bash
BASE=http://127.0.0.1:8000
```

## Formato de erro

Todas as falhas usam o mesmo envelope:

```json
{
  "detail": {
    "code": "invalid_filter_column",
    "message": "A coluna 'foo' não existe no dataset 'locais'.",
    "context": {"dataset": "locais", "column": "foo"}
  }
}
```

Códigos HTTP usados:

| Status | Quando |
|--------|--------|
| `400` | parâmetro inválido (coluna, agregação, `sort`, `limit`, etc.) |
| `404` | dataset, registro ou modelo inexistente |
| `500` | arquivo corrompido ou erro interno controlado (sem stack trace no corpo) |

## Health

### `GET /health`

```bash
curl -s "$BASE/health" | python -m json.tool
```

Resposta resumida:

```json
{
  "status": "ok",
  "app": "Feynman's Legacy API",
  "version": "1.0.0",
  "environment": "development",
  "uptime_seconds": 12.4,
  "data_dir": ".../data/tratados",
  "data_dir_exists": true,
  "models_dir": ".../models",
  "models_dir_exists": true
}
```

## Datasets

### `GET /api/v1/datasets`

Lista os datasets encontrados, com colunas, contagem e data de atualização.

```bash
curl -s "$BASE/api/v1/datasets" | python -m json.tool
```

```json
{
  "items": [
    {
      "name": "locais",
      "file": "locais.csv",
      "format": "csv",
      "description": "Análogos terrestres de referência.",
      "columns": [
        {"name": "id", "dtype": "int64", "description": null},
        {"name": "score", "dtype": "double", "description": "Similaridade entre 0 e 1."}
      ],
      "row_count": 6,
      "updated_at": "2026-11-14T12:00:00Z",
      "size_bytes": 512,
      "id_column": "id",
      "tags": ["análogos"],
      "readable": true,
      "error": null,
      "metadata": {"source": "ETL"}
    }
  ],
  "total": 1
}
```

Observações:

- O `name` é o caminho relativo sem extensão. Um arquivo
  `data/tratados/case1/ranking.csv` vira `case1/ranking`.
- Se o mesmo nome existir em CSV e Parquet, **Parquet tem prioridade**.
- Arquivos ilegíveis aparecem com `readable: false`, `row_count: null` e um
  `error` controlado; a leitura do dataset específico retorna `500`.
- Sidecar opcional: `data/tratados/<nome>.meta.json` ou
  `data/tratados/<arquivo>.meta.json`.

Exemplo de sidecar de dataset:

```json
{
  "description": "Análogos terrestres de referência.",
  "id_column": "id",
  "tags": ["análogos", "terrestres"],
  "source": "ETL",
  "columns": {"score": "Similaridade entre 0 e 1."}
}
```

### `GET /api/v1/datasets/{dataset}`

```bash
curl -s "$BASE/api/v1/datasets/locais" | python -m json.tool
curl -s "$BASE/api/v1/datasets/case1/ranking" | python -m json.tool
```

Dataset inexistente:

```bash
curl -i -s "$BASE/api/v1/datasets/nao_existe"
# HTTP/1.1 404 Not Found
```

## Registros

### `GET /api/v1/datasets/{dataset}/records`

Paginação:

```bash
curl -s "$BASE/api/v1/datasets/locais/records?limit=2&offset=2" | python -m json.tool
```

```json
{
  "dataset": "locais",
  "items": [{"id": 3, "nome": "Dry Valleys", "score": 0.65}],
  "total": 6,
  "limit": 2,
  "offset": 2,
  "fields": null,
  "sort": null,
  "order": null
}
```

Filtros dinâmicos (`?coluna=valor`):

```bash
# Igualdade simples
curl -s "$BASE/api/v1/datasets/locais/records?clima=arido"

# Filtros em colunas diferentes são AND
curl -s "$BASE/api/v1/datasets/locais/records?clima=arido&ativo=true"

# Repetir a mesma coluna combina os valores com OR
curl -s "$BASE/api/v1/datasets/locais/records?clima=arido&clima=polar"

# Valores ausentes
curl -s "$BASE/api/v1/datasets/locais/records?score=null"

# Se o dataset tiver uma coluna chamada "limit", use o prefixo filter_
curl -s "$BASE/api/v1/datasets/meu_dataset/records?filter_limit=10"
```

Ordenação, projeção e paginação na mesma chamada:

```bash
curl -s "$BASE/api/v1/datasets/locais/records?clima=arido&sort=score&order=desc&fields=id,nome,score&limit=2&offset=0"
```

Parâmetros:

| Parâmetro | Descrição |
|-----------|-----------|
| `limit` | tamanho da página; padrão `FL_DEFAULT_LIMIT` (100), máximo `FL_MAX_LIMIT` (1000) |
| `offset` | deslocamento base zero |
| `sort` | coluna de ordenação (validada) |
| `order` | `asc` ou `desc` (só pode ser usado com `sort`) |
| `fields` | colunas separadas por vírgula, na ordem desejada |
| `?coluna=valor` | filtro de igualdade, com coerção por tipo (`int`, `float`, `bool`, `datetime`, texto) |

Erros de parâmetro:

```bash
curl -i -s "$BASE/api/v1/datasets/locais/records?nao_existe=1"
# HTTP/1.1 400 Bad Request
# {"detail":{"code":"invalid_filter_column", ...}}
```

### `GET /api/v1/datasets/{dataset}/records/{id}`

```bash
curl -s "$BASE/api/v1/datasets/locais/records/2" | python -m json.tool
```

```json
{
  "dataset": "locais",
  "id": "2",
  "id_column": "id",
  "record": {"id": 2, "nome": "Askja", "clima": "frio", "score": 0.77}
}
```

A coluna de ID é, em ordem de prioridade:

1. `id_column` do sidecar;
2. nome convencional (`id`, `uuid`, `record_id`, `codigo`, `code`, `index`);
3. primeira coluna do dataset.

### `GET /api/v1/datasets/{dataset}/aggregations`

Contagem total:

```bash
curl -s "$BASE/api/v1/datasets/locais/aggregations?agg=count" | python -m json.tool
```

```json
{
  "dataset": "locais",
  "aggregations": ["count"],
  "columns": [],
  "group_by": [],
  "items": [{"group": {}, "values": {"count": 6}}],
  "total_groups": 1,
  "limit": 100,
  "offset": 0
}
```

Contagem agrupada, com paginação de grupos:

```bash
curl -s "$BASE/api/v1/datasets/locais/aggregations?agg=count&group_by=clima&limit=2&offset=0"
```

Múltiplas métricas e colunas (chaves no formato `<agregação>_<coluna>`):

```bash
curl -s "$BASE/api/v1/datasets/locais/aggregations?agg=min&agg=max&column=score"
```

Média por grupo, aplicando filtros antes:

```bash
curl -s "$BASE/api/v1/datasets/locais/aggregations?agg=mean&column=score&group_by=clima&clima=arido"
```

```json
{
  "items": [
    {"group": {"clima": "arido"}, "values": {"mean_score": 0.865}}
  ],
  "total_groups": 1
}
```

Agregações suportadas: `count`, `mean`, `min`, `max`, `sum`.

- `mean` e `sum` exigem `column` numérica.
- `count` sem `column` conta linhas; com `column`, conta valores não nulos.
- `group_by` aceita uma ou mais colunas (repetidas ou separadas por vírgula).
- Filtros dinâmicos funcionam como em `/records`.

## Modelos

### `GET /api/v1/models`

```bash
curl -s "$BASE/api/v1/models" | python -m json.tool
```

Os artefatos são descobertos por extensão (`.joblib`, `.pkl`, `.onnx`, `.pt`,
`.json`, `.ubj`, `.lgb`, `.xgb`, etc.) e **não são carregados**. Sidecar
opcional: `models/<nome>.meta.json` ou `models/<arquivo>.meta.json`.

Exemplo:

```json
{
  "items": [
    {
      "name": "cluster_kmeans",
      "file": "cluster_kmeans.joblib",
      "format": "joblib",
      "description": "KMeans dos análogos terrestres.",
      "size_bytes": 1024,
      "updated_at": "2026-11-14T12:00:00Z",
      "tags": ["clusterização"],
      "algorithm": "KMeans",
      "framework": "scikit-learn",
      "target": "cluster",
      "trained_at": "2026-11-01",
      "metrics": {"silhouette": 0.42},
      "params": {"n_clusters": 4},
      "metadata": {}
    }
  ],
  "total": 1
}
```

### `GET /api/v1/models/{nome}`

```bash
curl -s "$BASE/api/v1/models/cluster_kmeans" | python -m json.tool
curl -s "$BASE/api/v1/models/previsao/xgboost" | python -m json.tool
curl -i -s "$BASE/api/v1/models/nao_existe"
# HTTP/1.1 404 Not Found
```

## Análogos

Relações prontas entre as bases da Lua e de Marte e locais da Terra, para o
mapa 3D. As tabelas ficam em `data/tratados/analogos/` (também acessíveis pelas
rotas genéricas, ex.: `/api/v1/datasets/analogos/pares/records`).

### Como são gerados

```bash
make analogos                     # ou: python scripts/gerar_analogos.py
python scripts/nomear_locais.py   # opcional: nomeia locais novos (OpenStreetMap)
```

1. A Terra usa a média dos últimos 12 meses observados das variáveis mensais e
   as variáveis estáticas.
2. Cada base é comparada com todas as células terrestres pelo ranking do
   Notebook 03 (`recommend`), no perfil completo e em cada nicho.
3. Para cada base são escolhidos, sem repetir locais a menos de 500 km:
   - `geral`: as 8 melhores notas gerais;
   - `especialista`: até 2 locais com nota ≥ 80 em cada nicho, mesmo com nota
     geral baixa (ex.: ótimo em geologia e ruim em clima);
   - `destaque`: os locais padrão de `config/locais_destaque.json`, comparados com
     todas as bases.
4. Os análogos clássicos de `config/analogos_classicos.json` (Atacama, Dry
   Valleys, Devon, Islândia, Mojave...) e células cobertas por água ficam fora da
   seleção automática.
5. A série mensal da nota usa os meses observados e as previsões do LightGBM
   (`data/terra/analise_analogos/previsoes.parquet`).

As coordenadas das bases em `config/bases_espaciais.json` são aproximadas (ponto
representativo do sítio). Longitudes sempre leste, em [-180, 180].

| Tabela | Conteúdo |
|--------|----------|
| `bases` | 8 bases (2 Lua, 6 Marte) com ponto e raio no globo |
| `locais` | locais terrestres com nome, coordenadas e clima médio |
| `pares` | base ↔ local, tipo, nota geral, pontos fortes e fracos |
| `pares_nichos` | nota de cada par em cada nicho |
| `series` | nota geral mensal de cada par (observada e prevista) |

### `GET /api/v1/analogos/bases`

```bash
curl -s "$BASE/api/v1/analogos/bases?corpo=marte" | python -m json.tool
```

### `GET /api/v1/analogos/bases/{base_id}`

Rota principal do mapa 3D: a base (alvo) e os locais terrestres (análogos).

```bash
curl -s "$BASE/api/v1/analogos/bases/MARTE_JEZERO?limit=5" | python -m json.tool
curl -s "$BASE/api/v1/analogos/bases/MARTE_GALE?forte_em=geologia"
curl -s "$BASE/api/v1/analogos/bases/LUA_POLO_SUL?destaque=true"
```

| Parâmetro | Descrição |
|-----------|-----------|
| `tipo` | `destaque`, `geral` ou `especialista` |
| `destaque` | `true` só locais padrão |
| `forte_em` | nicho (`termico`, `geologia`, `terreno`...) em que o local é forte |
| `nota_minima` | nota geral mínima (0–100) |
| `limit` | máximo de pares; `total` traz a contagem antes do limite |

```json
{
  "base": {
    "base_id": "MARTE_JEZERO", "corpo": "marte", "nome": "Cratera Jezero",
    "latitude": 18.38, "longitude": 77.58, "raio_km": 150.0, "n_pares": 38
  },
  "pares": [
    {
      "par_id": "MARTE_JEZERO__T042068", "tipo": "destaque", "rank_base": 1,
      "nota_geral": 83.85, "cobertura": 1.0,
      "pontos_fortes": ["agua_gelo", "subsuperficie", "biologia_habitabilidade"],
      "pontos_fracos": ["atmosfera", "termico"],
      "nichos": {"termico": 20.86, "geologia": 87.5, "terreno": 86.46, "atmosfera": 0.0},
      "local": {
        "location_id": "T042068", "nome": "Deserto da Núbia — Sudão",
        "latitude": 20.75, "longitude": 33.25, "raio_km": 150.0, "destaque": true
      }
    }
  ],
  "total": 38
}
```

### Custo-benefício: EUA, bases de apoio e rotas alternativas

A logística usa o catálogo `data/terra/apoio/nasa_bases_suporte.parquet` (182
bases da NASA, agências parceiras e contratadas). Bases com vínculo `Restrita`
e zonas no oceano ficam fora do cálculo. Os pesos estão em
`config/custo_beneficio.json`:

| Parte | Fórmula padrão | Peso |
|-------|----------------|------|
| `nota_eua` | 100 · exp(−distância à instalação dos EUA mais próxima / 3000 km) | 0,40 |
| `nota_apoio` | 100 · max(prioridade · exp(−distância / 1000 km)) | 0,35 |
| `nota_rotas` | 100 · min(1, Σ prioridade das bases a até 2500 km / 3) | 0,25 |

`custo_beneficio = raiz(nota_geral × nota_logistica)`. Para cada base entram no
top os 8 melhores locais (500 km entre si, fora dos clássicos) com nota geral
de pelo menos 80% da melhor nota daquela base, para que a logística não esconda
um análogo ruim. Esses pares têm `tipo = custo_beneficio` ou, se já existiam,
`top_custo_beneficio = true`.

```bash
# Melhores custo-benefício (todas as bases, só o top)
curl -s "$BASE/api/v1/analogos/custo-beneficio"

# Por base ou corpo; apenas_top=false lista todos os pares com nota
curl -s "$BASE/api/v1/analogos/custo-beneficio?base_id=MARTE_GALE&limit=5"
curl -s "$BASE/api/v1/analogos/custo-beneficio?corpo=lua&apenas_top=false"

# Pares de uma base ordenados por custo-benefício
curl -s "$BASE/api/v1/analogos/bases/LUA_POLO_SUL?ordenar=custo_beneficio"

# Bases de apoio para marcar no globo
curl -s "$BASE/api/v1/analogos/apoios?usado=true"
```

Cada item de `/custo-beneficio` traz `local` (com `nota_logistica`,
`distancia_eua_km`, `apoio_principal_nome`, `n_apoios_raio`), `base` e `rotas`:

```json
{
  "par_id": "MARTE_GALE__T085720", "custo_beneficio": 88.0,
  "nota_geral": 78.8, "nota_logistica": 98.3,
  "local": {"nome": "White Sands — Novo México, EUA", "distancia_eua_km": 10.9},
  "rotas": [
    {"ordem": 1, "tipo_rota": "principal", "nome": "White Sands Complex (STGT/WSGT) – TDRS",
     "distancia_km": 46, "latitude": 32.5, "longitude": -106.6},
    {"ordem": 2, "tipo_rota": "alternativa", "nome": "White Sands Missile Range – LC-36",
     "distancia_km": 51},
    {"ordem": 3, "tipo_rota": "alternativa", "nome": "White Sands Test Facility (WSTF)",
     "distancia_km": 50}
  ]
}
```

As distâncias são em linha reta (grande círculo), não por estrada; servem para
comparar locais e desenhar os arcos no 3D.

### Outras rotas

```bash
# Locais padrão do software (destaques)
curl -s "$BASE/api/v1/analogos/locais?destaque=true"

# Todas as bases relacionadas a um local terrestre
curl -s "$BASE/api/v1/analogos/locais/T042068"

# Par completo com a série mensal (observada + prevista)
curl -s "$BASE/api/v1/analogos/pares/MARTE_JEZERO__T042068"

# Nomes legíveis dos nichos
curl -s "$BASE/api/v1/analogos/nichos"
```

Uso no front (Three.js): `base.latitude/longitude/raio_km` vai no corpo
(Marte ou Lua) e `pares[].local.latitude/longitude/raio_km` na Terra, no mesmo
formato `{name, lat, lon, radiusKm}` do `CONFIG` de `mapa.ts`.

Erros: `404 analogs_not_generated` quando as tabelas não existem;
`404 base_not_found`, `local_not_found` e `pair_not_found` para IDs inválidos.

## CORS

As origens são configuradas por `FL_CORS_ORIGINS` (lista JSON ou valores
separados por vírgula). Em produção, `*` é rejeitado na inicialização.

```dotenv
FL_CORS_ORIGINS=["https://app.exemplo.org"]
```

`OPTIONS` (preflight) é respondido para `GET` e as respostas expõem
`X-Request-ID` e `X-Process-Time-Ms`.

## Observabilidade

- Logs estruturados em JSON (`FL_LOG_LEVEL`).
- Cada resposta traz `X-Request-ID` (aceita o header enviado pelo cliente) e
  `X-Process-Time-Ms`.
- Erros `500` não expõem stack trace no corpo; o detalhe fica nos logs.

## Testes

```bash
make api-test
# ou
python -m pytest tests -q
```
