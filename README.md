# Feynman's Legacy

**Tema:** Identificar locais na Terra que sejam análogos aos locais de uma base lunar permanente e de Marte.

Os estudos são feitos em notebooks (`.ipynb`) e consolidados em uma aplicação web para visualização dos achados.

## Casos de estudo

| # | Caso | Objetivo | Status |
|---|------|----------|--------|
| 1 | Clusterização atual | Identificar locais potenciais com scoring de similaridade | Em andamento |
| 2 | Modelo de previsão | Prever similaridade futura a partir de condições históricas | Planejado |
| 3 | A definir | Pendente | Pendente |

## Estrutura do repositório

```
feynmans-legacy/
├── app/                      # API FastAPI (back-end somente leitura)
│   ├── routers/              # health, datasets e models
│   ├── schemas/              # contrato Pydantic v2
│   ├── services/             # leitura/cache de CSV/Parquet e artefatos
│   ├── config.py             # configuração por variáveis FL_*
│   └── main.py               # create_app / instância ASGI
├── data/
│   ├── marte/               # Dados e spec de referência de Marte
│   ├── lua/                 # Spec de referência da Lua
│   └── terra/               # Dados temáticos, insumos e resultados da análise
├── config/                   # Nichos e critérios de comparação entre corpos
├── docs/
│   ├── decisions/            # Registro de decisões técnicas (ADRs)
│   ├── api.md                # Exemplos de curl de cada endpoint
│   └── methodology.md        # Metodologia dos estudos
├── models/                   # Artefatos de modelos treinados
├── notebooks/
│   └── 00_ETL/               # Extração, transformação e carga
├── src/feynmans_legacy/
│   ├── features/             # Engenharia de atributos
│   └── models/               # Clusterização e previsão
├── tests/                    # Testes de contrato da API
├── .github/                  # Workflows e templates
├── Makefile                  # Atalhos de comandos
└── pyproject.toml            # Dependências e configuração
```

## Como começar

```bash
git clone https://github.com/jose-aquino-jr/feynmans-legacy.git
cd feynmans-legacy
make setup
pre-commit install
```

## Criação e ativação da venv

```bash
python -m venv .venv
source .venv/Scripts/activate      # no Windows; em Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .                   # instala o pacote src/feynmans_legacy
python -m ipykernel install --user --name feynmans-legacy
pre-commit install
```

## API (FastAPI)

A API expõe rotas genéricas **somente leitura** sobre `data/tratados/` e os
metadados de `models/`. Não há front-end, autenticação implementada nem
endpoints de escrita nesta etapa.

```bash
cp .env.example .env          # no Windows: copy .env.example .env
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
uvicorn app.main:app --reload
```

- Swagger: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health: <http://127.0.0.1:8000/health>
- Exemplos de `curl`: [`docs/api.md`](docs/api.md)

Atalhos:

```bash
make api-dev     # uvicorn app.main:app --reload
make api-test    # pytest tests -q
make api-lint    # ruff check app tests && mypy
```

Endpoints principais:

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | status e disponibilidade dos diretórios |
| GET | `/api/v1/datasets` | lista datasets e metadados |
| GET | `/api/v1/datasets/{dataset}` | metadados de um dataset |
| GET | `/api/v1/datasets/{dataset}/records` | registros paginados, filtros, sort e fields |
| GET | `/api/v1/datasets/{dataset}/records/{id}` | registro pelo identificador |
| GET | `/api/v1/datasets/{dataset}/aggregations` | `count`, `mean`, `min`, `max`, `sum` + `group_by` |
| GET | `/api/v1/models` | metadados dos artefatos |
| GET | `/api/v1/models/{nome}` | metadados de um artefato |
| GET | `/api/v1/analogos/bases` | bases da Lua e de Marte com o ponto no globo |
| GET | `/api/v1/analogos/bases/{base_id}` | locais terrestres relacionados, com notas por nicho |
| GET | `/api/v1/analogos/locais` | locais terrestres (`destaque=true` = padrão do software) |
| GET | `/api/v1/analogos/locais/{location_id}` | bases relacionadas a um local terrestre |
| GET | `/api/v1/analogos/pares/{par_id}` | par completo com a nota mensal observada e prevista |
| GET | `/api/v1/analogos/nichos` | nichos de comparação e nomes legíveis |

Os análogos são gerados por `make analogos` (ou `python scripts/gerar_analogos.py`)
depois dos notebooks 01 e 02. Veja [`docs/api.md`](docs/api.md#análogos).

A configuração vem de variáveis `FL_*` (veja `.env.example`): diretórios,
limites de paginação, origens de CORS e nível de log. Se `data/tratados/`
ainda não existir, a listagem retorna `{"items": [], "total": 0}`; a API não
cria nem altera dados.

## Fluxo de trabalho

1. **ETL:** mantenha os dados na pasta do corpo correspondente. Os arquivos temáticos da Terra ficam em `data/terra/nichos/`. A análise lê `data/terra/terra.parquet`, os insumos auxiliares em `data/terra/spec_analogos/` e as referências fixas em `data/lua/` e `data/marte/`.
2. **Estudos:** cada caso tem seus notebooks numerados (ex.: `01_01_features.ipynb`). Lógica reutilizável vai para `src/feynmans_legacy`, não fica só no notebook.
3. **Aplicação:** o `app` consome `data/terra/terra.parquet`, os resultados de `data/terra/analise_analogos/`, `config/nichos.json` e os perfis de referência espaciais.

## Convenções

- **Branches:** `case1/descricao`, `case2/descricao`, `app/descricao`, `setup/descricao`.
- **Commits:** `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.
- **Notebooks:** sem outputs versionados (`nbstripout`) e com seeds fixas.
- **Dados:** não versionar arquivos pesados; documentar fonte, licença e data de download nos catálogos [Terra](data/terra/README.md) e [Marte](data/marte/catalogo.md).
- **PRs:** sempre para `main`, com revisão de pelo menos uma pessoa.

## Equipe

| Frente | Responsável |
|--------|-------------|
| Dados / ETL | _a definir_ |
| Caso 1 | _a definir_ |
| Caso 2 | _a definir_ |
| Aplicação | _a definir_ |

## Licença

_A definir._