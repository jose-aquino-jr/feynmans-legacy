# Nichos e perfis de referência

Os notebooks usam `data/terra/terra.parquet` como série mensal por
`location_id` e `anomes` e associam `spec_analogos/estaticas.parquet` pelo ID. Os Parquets
temáticos em `data/terra/nichos/` servem à exploração e ao ETL. Os nichos selecionam
colunas da tabela consolidada, inclusive quando compartilham uma variável.

| Arquivo | Papel |
|---|---|
| `nichos.json` | Corpo → nicho → variável terrestre, coluna do perfil, tolerância e peso. |
| `criterios_referencia_proposta.csv` | Registra o alvo por base, a regra de derivação e os parâmetros de cada critério. |
| `../data/lua/lua.parquet` | Perfis propostos de duas bases lunares para o ranking. |
| `../data/marte/marte.parquet` | Perfis propostos de seis bases marcianas para o ranking. |
| `../data/lua/outputs/lua.parquet` | Export científico por região lunar, acompanhado de `lua_columns.csv`. |

O Notebook 01 verifica o vínculo entre os nomes das variáveis, as colunas
numéricas da Terra, a unidade declarada no dicionário e os valores do catálogo,
dos perfis e do JSON. A nota de cada variável usa a distância ao alvo dividida
pela tolerância, ambos expressos na unidade da medida terrestre para o critério.

A proposta atual usa alvos fixos e percentis da distribuição terrestre. A
coerência de tipos, unidades declaradas e configuração permite executar o
ranking. Para fundamentar uma correspondência científica, registre também
grandeza, unidade de origem, conversão, escala espacial, período de agregação e
justificativa do proxy, quando houver. Por exemplo, converter Kelvin em °C
alinha a unidade, enquanto a temperatura de brilho da superfície e a temperatura
do ar a 2 m continuam sendo grandezas diferentes. Relevo e declividade
podem ser avaliados após alinhar resolução e método. Elevação em relação a
referenciais planetários distintos exige uma definição de comparação.

Para integrar um novo perfil, use o dicionário científico, selecione as bases,
documente a correspondência e atualize em conjunto o Parquet de perfil,
`nichos.json` e o catálogo CSV. Execute os notebooks 01 → 02 → 03.

## Valores reais da Lua e de Marte

`valores_reais.csv` registra, por base e variável, o valor real com unidade,
grandeza, confiança (`alta`, `media`, `baixa`) e fonte (missão, artigo ou
cálculo). `python scripts/aplicar_valores_reais.py` grava esses alvos em
`data/lua/lua.parquet` e `data/marte/marte.parquet` e atualiza o catálogo
(o valor anterior fica em `alvo_proxy`).

Como muitos valores reais estão fora do alcance da Terra (pressão de Marte ≈
0,7 kPa, Lua ≈ 0 kPa), a tolerância desses alvos é própria de cada base
(`<variável>__tolerancia` no Parquet): a maior distância entre o alvo e os
percentis 1 e 99 da Terra. A nota continua `100 × (1 − |valor − alvo| /
tolerância)`, então o lugar da Terra mais próximo do valor real pontua e os
demais caem proporcionalmente. Sem essa coluna vale a tolerância de
`nichos.json`.

| Tipo de alvo | Quando | Exemplos |
|---|---|---|
| real | há medida ou cálculo físico com fonte | pressão, temperatura, radiação, altura do Sol, NDVI, chuva, carbono orgânico, vento, pH (Phoenix) |
| classificação | presença/ausência definida pela geologia do sítio | litologias, permafrost, tubos de lava, solo exposto, terreno plano, albedo |
| equivalente terrestre | sem medida comparável na mesma escala | relevo, declividade, posição topográfica e elevação (MOLA/LOLA ≠ nível do mar, escala de 0,5°), poeira em µg/m³, temperatura e amplitude no polo lunar |

Depois de aplicar os valores reais, rode `make analogos` para regenerar os pares.
