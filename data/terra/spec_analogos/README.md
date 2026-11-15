# spec_analogos — insumos dos notebooks 01 → 02 → 03

Pasta de insumos terrestres no **contrato de entrada** de `feynmans-legacy` (`data/terra/spec_analogos/`). Validada com as funções
originais de `src/feynmans_legacy/analog_study.py` (branch `feature/notebooks-estudo`), reproduzindo os Notebooks 01, 02 e 03.

| Arquivo | Chave | Conteúdo |
|---|---|---|
| `data/terra/terra.parquet` | `location_id, anomes` | 85.726 locais × 92 meses (**201901–202608**) = 7.886.792 linhas, 16 variáveis dinâmicas mensais |
| `estaticas.parquet` | `location_id` | 67 atributos invariantes: relevo, litologia, solo, pressão por altitude, geometria solar, cobertura do solo, eventos, permafrost |
| `coordenadas.parquet` | `location_id` | `latitude`, `longitude` (float64, WGS84, graus decimais) |
| `data/lua/lua.parquet` | `base_id` | 2 bases: `LUA_POLO_SUL`, `LUA_MARE_TUBOS` — **PROPOSTA** |
| `data/marte/marte.parquet` | `base_id` | 6 bases: `MARTE_JEZERO`, `MARTE_GALE`, `MARTE_MERIDIANI`, `MARTE_GELO_MEDIAS_LAT`, `MARTE_THARSIS_TUBOS`, `MARTE_MEDUSAE_YARDANGS` — **PROPOSTA** |
| `config/nichos.json` | corpo → nicho → variável | Lua: 9 nichos; Marte: 12 nichos; 34 variáveis distintas — **PROPOSTA** |

O Notebook 01 confere o dicionário `dicionario_spec.csv` e o catálogo `config/criterios_referencia_proposta.csv`. `cobertura_terra_por_mes.csv` e `manifesto.json` documentam a cobertura e a publicação.

## Chaves e IDs

- `location_id` é texto `T` + 6 dígitos (`T000001`…`T085726`), igual nas três tabelas terrestres e nas pastas por tema de `data/`.
  Leia como texto para preservar os zeros à esquerda.
- `T000001`…`T085699` são centros exatos das células de terra de uma grade de 0,5°. `T085700`…`T085726` são os
  27 sítios nomeados do projeto, nas coordenadas exatas deles. Nomes e países estão em `data/terra/nichos/coordenadas/coordenadas.parquet`.
- `anomes` é `int32` no formato YYYYMM.
- `terra.parquet` está ordenado por `location_id` e depois por `anomes`.

## Como cada valor mensal foi produzido

- **Fonte:** produto **mensal** da NASA via GIBS (MERRA-2 e MODIS Terra), decodificado pelo colormap oficial de cada camada.
- **Valor da célula:** mediana dos pixels de 0,25° dentro da janela de 0,5° centrada no local.
- **Arredondamento:** à precisão do colormap. Os limites de cada variável estão na coluna `descricao` do dicionário;
  valores no limite significam "≤" ou "≥" (ex.: temperatura do ar ≤ −53 °C, poeira ≥ 90 µg/m³).
- **Sem preenchimento:** meses que a fonte não publica ficam ausentes:
  - temperatura MERRA-2: 202312, 202401 e 202405;
  - NDVI: 202504.
- **Derivada:** `temperatura__lst_amplitude_dia_noite_c` = LST dia − LST noite do mesmo mês.

## Controle de qualidade

- Auditoria das camadas: 100% dos pixels válidos correspondem ao colormap publicado.
- Removido por erro de fonte:
  - CERES: a paleta do WMS é diferente da publicada;
  - pressão MERRA-2: satura em ≤800 e ≥1020 hPa e foi trocada por `poeira_vento_processos__pressao_estimada_altitude_kpa`
    (atmosfera padrão sobre a elevação);
  - temperatura skin MERRA-2: satura em ≤ −33 °C;
  - cobertura de neve MODIS: "0%" e "sem observação" chegam iguais.
- Checagem cruzada com a NASA POWER nos 27 sítios: temperatura com correlação de 0,999 (erro médio 0,8 °C);
  chuva e vento com correlação de 0,93 a 0,96.

## O que a validação mostrou (`validar_spec_analogos.py`)

- **Notebook 01:** os 6 arquivos foram lidos; as chaves estão sem nulos ou duplicatas; todo ID tem coordenada válida.
  Não há colunas repetidas entre `terra` e `estaticas`, e as 34 variáveis dos nichos existem.
  A seleção no mês 202608 aceitou 22 das 34 variáveis, e o k-means com k = 3 rodou.
- **Cobertura abaixo de 80%:** 7 variáveis (radiação, NDVI, albedo, carbono do solo, população, umidade do solo, pH)
  ficaram com ~70%. As fontes não cobrem calotas de gelo (Antártida e Groenlândia, ~30% dos locais).
  A regra de 80% do Notebook 01 as tira **só do agrupamento**; o ranking continua usando todas.
  Decidam com a equipe se querem baixar o limite ou excluir as calotas.
- **Notebook 02:** o LightGBM é treinado por variável dinâmica e horizonte, com amostra de 400 locais.
  O Optuna ajusta uma configuração por variável com dois meses de validação. O MAE é comparado
  com o LightGBM padrão e a persistência. Os três últimos meses ficam reservados para teste.
  Os resultados ficam em `metricas_previsao.parquet` e `otimizacao_lightgbm.json`.
  A inferência em lote preenche os horizontes de 1 a 3 meses para todos os locais com
  histórico suficiente e publica o resultado em `previsoes.parquet`.
- **Notebook 03:** `profile_criteria` + `recommend` rodaram para as 8 bases, em "Todos" e num nicho individual.
  Exemplos de primeiro colocado:

| Base | Primeiro colocado em "Todos" |
|---|---|
| LUA_POLO_SUL | Ártico canadense (ilha de Baffin) |
| LUA_MARE_TUBOS | Basaltos do Saara argelino e da Arábia |
| MARTE_JEZERO | Deserto Núbio (Sudão) |
| MARTE_GALE | Deserto de Mojave (EUA) |
| MARTE_MERIDIANI | Bacia do Tarim (China) |
| MARTE_GELO_MEDIAS_LAT | Costa sem gelo do norte da Groenlândia e Ártico canadense |
| MARTE_THARSIS_TUBOS | Puna e Altiplano andino |
| MARTE_MEDUSAE_YARDANGS | Deserto de Lut (Irã) |

## Proposta a validar com a equipe

Consulte [a configuração de referência](../../../config/README.md).

O handoff diz que alvos, tolerâncias e pesos são definidos pela equipe. Estes arquivos são um **ponto de partida que roda**:

- **Alvo:** é o **valor terrestre mais parecido com o corpo**. Pode ser um número fixo (ex.: litologia de basalto = 1)
  ou um percentil da distribuição terrestre (ex.: pressão = p0, a menor pressão da Terra; precipitação = p1).
  O percentil é usado quando a condição real (vácuo, −170 °C) não existe na Terra.
- **Tolerância:** é única por corpo e variável, como o leitor atual exige. Vale p95 − p5 dos valores terrestres,
  ou 1 para as variáveis 0/1.
- **Peso:** 1 em todas as variáveis.
- A regra de cada número está em `criterios_referencia_proposta.csv`.

## Commit

`terra.parquet` tem ~87 MB, abaixo do limite de 100 MB por arquivo do GitHub, mas acima do aviso de 50 MB.
O handoff pede para **não** versionar dados processados: confirmem com a equipe se vai para o repositório,
Git LFS ou uma release.

## Regenerar

```bash
python construir_dataset_terra.py
```

```bash
python exportar_spec_analogos.py --inicio 201901 --fim 202608
```

```bash
python validar_spec_analogos.py --repo CAMINHO/DO/feynmans-legacy
```

O primeiro comando gera `data/dataset_ml` (~2 h na primeira vez, por causa da geologia; depois ~4 min com cache).
O segundo gera os insumos (~9 min com cache). Se o exportador usar o layout anterior, distribua as specs conforme a tabela acima. O terceiro valida com o código da equipe.
