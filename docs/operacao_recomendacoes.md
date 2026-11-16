# Operação das recomendações temporais

Guia para publicar dados, trocar o modelo, rodar API e front e reproduzir os
resultados de `GET /api/v1/analogos/recomendacoes`.

## 1. Como funciona

```
perfis fixos (data/lua, data/marte) + config/nichos.json ───────────────┐
                                                                        │
AAAAMM ─→ observado (terra.parquet) | projeção recursiva (cache) | sazonal ├─→ recommend() por base ─→ top K
          + estaticas.parquet + coordenadas.parquet ────────────────────┘                 │
          clusters.parquet ─→ contexto (anomes_cluster)                                     ↓
                                                                        FastAPI ─→ Angular + globo
```

- **Mês observado** (até o corte): valores reais do mês.
- **Mês futuro, `estrategia=recursiva`** (padrão do front): o motor
  `src/feynmans_legacy/forecast_projection.py` projeta mês a mês. Para o mês `t`
  usa o maior horizonte direto `h` com modelo e `h <= t − corte`, com features
  na origem `t − h`; os lags vêm das observações ou de meses já projetados.
  Sem horizonte que caiba (hoje: NDVI em H1/H2), usa o mesmo mês do ano
  anterior e declara `sazonal_t-12`. Origem `prevista` até H3 e `extrapolada`
  depois, com rótulo **Projeção exploratória**.
- **`estrategia=auto`** (legado): direto até H3 e, depois, cenário sazonal.
- **`estrategia=sazonal`**: o mesmo mês no último ano observado
  (`mes_base_cenario`). Nunca grava nem lê a trajetória recursiva.
- O mês nunca altera o perfil da base; só o estado da Terra muda.

## 2. Inventário da publicação (corte 202608)

Contagens derivadas dos arquivos por `scripts/publicar_projecoes.py` e
registradas em `data/terra/analise_analogos/manifesto_publicacao.json`.

| Caminho | Papel | Chave | Cobertura / período | Consumidor |
|---|---|---|---|---|
| `data/terra/terra.parquet` | histórico mensal (16 variáveis dinâmicas) | `(location_id, anomes)`, 0 duplicadas | 85.726 locais × 92 meses (201901–202608), 7.886.792 linhas | projeção, ranking observado |
| `data/terra/analise_analogos/estaticas.parquet` | variáveis estáticas (67) | `location_id` único | 85.726 | ranking (join) |
| `data/terra/analise_analogos/coordenadas.parquet` | de-para ID → lat/lon (−180..180) | `location_id` único, texto de 7 caracteres | 85.726; lat −89,75..83,25 | ranking, globo |
| `data/terra/analise_analogos/clusters.parquet` | rótulo K-Means | `(location_id, anomes)` | 85.726, anomes 202608 | contexto `cluster` |
| `data/terra/analise_analogos/modelos/previsao_mensal.pkl` | LightGBM por `(variável, H)` (Git LFS) | 25 modelos, H1–H3 | NDVI só H3 | projeção |
| `data/terra/analise_analogos/metricas_previsao.parquet`, `otimizacao_lightgbm.json` | auditoria do treino | — | treino até 2026-03, validação 2026-04/05, teste 2026-06/08 | relatório |
| `data/lua/lua.parquet`, `data/marte/marte.parquet` | perfis fixos (alvos e tolerâncias por base) | `base_id` | 2 + 6 bases | ranking |
| `config/nichos.json` | variável terrestre ↔ alvo, tolerância, peso por corpo/nicho | — | 9 nichos (Lua), 12 (Marte) | ranking |
| `config/bases_espaciais.json` | nome e posição das bases | `base_id` | 8 | `/opcoes`, globo |
| `config/valores_reais.csv`, `config/criterios_referencia_proposta.csv` | fonte e tipo de cada alvo | `(base_id, variável)` | 77 alvos reais | `criterios[].tipo_alvo/fonte` |
| `data/terra/analise_analogos/cache_projecoes/<trajetória>/` | meses projetados (float32) + `meses.json` + `manifesto.json` | `location_id` | ~1,8 MB por mês | API (fora do Git) |

`coordenadas.parquet` e `estaticas.parquet` de `analise_analogos/` são cópias
idênticas das de `spec_analogos/` (conferido nesta publicação).

## 3. Rodar localmente

```bash
git lfs pull                      # o pickle do modelo é Git LFS
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
python scripts/publicar_projecoes.py           # 12 meses após o corte + manifesto
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Front (em `front-end/`):

```bash
npm ci
npm start          # ng serve em http://localhost:4200, proxy /api -> 127.0.0.1:8000
npm run build      # produção em front-end/dist/front-end
```

O proxy está em `front-end/proxy.conf.json`. Em produção, sirva o build e a API
na mesma origem (por exemplo um proxy reverso que manda `/api` para o uvicorn e o
resto para `dist/front-end/browser`).

Verificação:

```bash
ruff check .
python -m mypy
python -m pytest
cd front-end && npx ng test --watch=false && npx ng build
```

## 4. Configuração (`FL_*`)

| Variável | Padrão | Uso |
|---|---|---|
| `FL_RECOMENDACOES_TERRA_PATH` | `data/terra/terra.parquet` | histórico |
| `FL_RECOMENDACOES_RUN_DIR` | `data/terra/analise_analogos` | estáticas, coordenadas, clusters |
| `FL_RECOMENDACOES_MODELO_PATH` | `…/modelos/previsao_mensal.pkl` | pacote LightGBM (só de publicação confiável) |
| `FL_RECOMENDACOES_CACHE_DIR` | `…/cache_projecoes` | trajetórias materializadas |
| `FL_RECOMENDACOES_WORKERS` | `1` | threads de projeção |
| `FL_RECOMENDACOES_FILA_MAX` | `8` | tarefas simultâneas antes de responder 503 `fila_cheia` |
| `FL_RECOMENDACOES_RETRY_SEGUNDOS` | `5` | `Retry-After` do 202 |
| `FL_RECOMENDACOES_ANOMES_MAX` | `210012` | último mês aceito |
| `FL_RECOMENDACOES_LOTE_IDS` | `50000` | IDs por chamada de `predict` |

## 5. Fila, cache e durabilidade (um processo + disco)

- **Uma trajetória por publicação.** A chave é o hash de
  `(sha256 do pickle, sha256 do histórico, algoritmo, esquema, variáveis)`.
  Trocar modelo ou histórico gera outra pasta; a antiga pode ser apagada.
- **Checkpoint mensal atômico.** Cada mês é gravado em `AAAAMM.parquet` (arquivo
  temporário + `os.replace`) e só então entra em `meses.json`. Após restart, a
  tarefa continua do último mês contíguo. Retomar é idêntico a rodar do zero
  (teste `test_checkpoint_resume_equals_from_scratch`; valores em float32).
- **Deduplicação.** Pedidos simultâneos para a trajetória recebem a mesma
  `tarefa_id`; um destino mais distante estende a tarefa em andamento.
- **Reuso.** O estado do mês fica em cache (LRU de 4 meses) e serve qualquer
  base, nicho, cobertura, K e página; o ranking completo por
  `(estado, base, nicho, cobertura)` fica em LRU de 64 entradas.
- **Falha.** A tarefa vira `falhou`; por 60 s a API responde 500
  `projecao_falhou` com o erro; depois, o próximo pedido tenta de novo.
- **Cancelamento.** O cliente pode desistir; a tarefa continua e serve o próximo
  interessado.
- **Retenção.** A pasta cresce ~1,8 MB por mês projetado (julho de 2040 ≈ 294 MB).
  Apague pastas de trajetórias antigas; não há expiração automática.
- **Vários workers de API** exigiriam fila compartilhada e trava por trajetória
  (ex.: Redis + disco compartilhado). Fora do escopo desta entrega.

`GET /api/v1/analogos/recomendacoes/tarefas` lista as tarefas do processo.

## 6. Trocar o modelo ou os dados

1. Rode os notebooks 01 e 02 (gera `selecao.json`, clusters e o pickle).
2. Confira que a origem do pickle é o último mês de `terra.parquet`; se não for,
   a API responde 503 `publicacao_indisponivel`.
3. `python scripts/publicar_projecoes.py` (aquece 12 meses e grava o manifesto).
4. Reinicie a API (a publicação é carregada uma vez por processo).
5. Rollback: volte os arquivos (Git/LFS) e reinicie; a trajetória antiga é
   reutilizada porque a chave depende dos hashes.

Health: `GET /health`; publicação: `GET /api/v1/analogos/recomendacoes/opcoes`
(campo `publicacao` com corte, hashes e trajetória).

## 7. Medições desta entrega (Windows, 12 CPUs, Python 3.13, grade completa)

| Medida | Valor |
|---|---|
| Carga da publicação (primeira chamada) | 1,0–1,5 s |
| Projeção recursiva 202609 → 204007 (166 meses) | 497 s (~3,0 s/mês) |
| 204008 a partir do checkpoint de 204007 | 5,6 s |
| Admissão (202) | 27–86 ms |
| Observado 202608, 8 bases, K=10, frio | 7,8 s |
| 204007 Jezero térmico, frio (estado em disco) | 0,57 s |
| 204007 Jezero térmico, quente (20 repetições) | p50 77 ms, p95 192 ms |
| 204007 Lua Todos, offset 10 (mesma projeção) | 1,4 s |
| Cenário sazonal 204007, 8 bases, frio | 14,9 s (com o backtest rodando em paralelo) |
| Payload 8 bases × K=10 | ~290 KB |

Não medidos: memória e CPU por etapa, carga com vários clientes, renderização
no navegador. O ranking observado frio (7,8 s para 8 bases) é a etapa mais lenta
e o primeiro candidato a otimizar (pré-calcular o ranking por mês/nicho).
