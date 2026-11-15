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
