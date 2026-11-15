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
