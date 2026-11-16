# Estudo: recomendações temporais de análogos

## Pergunta

Dado um AAAAMM (inclusive futuro), quais locais da Terra mais se parecem com cada
base da Lua e de Marte? Os alvos das bases são fixos; muda o estado terrestre.

## Método

- **Similaridade** (`analog_study.recommend`, a mesma do Notebook 03):
  `nota_i = 100·max(0, 1 − |valor_i − alvo_i| / tolerância_i)`,
  `nota = Σ pesoᵢ·notaᵢ / Σ pesoᵢ` (critérios com dado),
  `cobertura = Σ pesoᵢ (com dado) / Σ pesoᵢ (perfil)`, mínimo 0,7 por padrão.
  Desempate por `location_id`. O teste `test_matches_reference_recommend` prova
  que a API devolve exatamente o ranking de `recommend()`.
- **Estado futuro**: LightGBM direto H1–H3 e extensão recursiva (seção 1 de
  `operacao_recomendacoes.md`); referência sazonal = mesmo mês do ano anterior.
- **Backtest** (`scripts/avaliar_projecoes.py`): 400 locais (semente 42),
  9 variáveis, cortes 2024-08, 2025-02 e 2025-08, modelos LightGBM padrão
  (100 árvores) retreinados por corte só com destinos `<= corte`; projeção
  recursiva até 12 meses alimentada pelas próprias previsões; comparação com o
  sazonal nas mesmas linhas válidas; top 10 de cada base (nicho Todos) com estado
  projetado × observado.

## Resultados do backtest

Mediana do ganho de MAE sobre o sazonal (positivo = LightGBM melhor) e acordo do
top 10 (arquivos em `data/terra/analise_analogos/avaliacao/`):

| Horizonte | Ganho de MAE | Acordo top 10 | Mesmo top 1 |
|---|---|---|---|
| H1 | **+13,1%** | 88,3% | 66,7% |
| H3 | −54,0% | 78,3% | 54,2% |
| H6 | −28,9% | 82,5% | 54,2% |
| H12 | −34,7% | 81,7% | 58,3% |

Por variável, o LightGBM só ganha do sazonal de forma consistente em H1
(umidade do solo +52%, amplitude térmica +22%, chuva +16%). Albedo e poeira
pioram muito a partir de H3 (−180% e −68%).

O estudo de referência do prompt (+12,68%, −62,54%, −23,86%, −26,20%; acordo
84,2/68,3/71,2/80,0%) tem a mesma forma; as diferenças vêm de outra amostra e
dos alvos reais (PR #13).

## Diagnóstico da projeção longa (julho de 2040, grade completa)

| Variável | Desvio-padrão jul/2026 obs. → jul/2040 proj. | Média | Nulos |
|---|---|---|---|
| amplitude térmica dia-noite | 4,86 → 0,04 °C | 4,46 → −0,18 | 0,4% → 3,5% |
| chuva | 2,49 → 0,88 mm/dia | 1,89 → 1,66 | — |
| albedo | 0,13 → 0,04 | 0,21 → 0,20 | 28% → 48% |
| NDVI | 0,27 → 0,13 | 0,54 → 0,65 | 31% → 46% |
| temperatura do ar | 31,1 → 31,4 °C | 0,91 → −4,25 °C | — |

A recursão perde variabilidade (a amplitude térmica colapsa para ~0), desloca a
média da temperatura em −5 °C e espalha nulos: um local sem um lag fica sem
valor em todos os meses seguintes. Por isso, em 204007, o nicho térmico de
Jezero tem nota máxima ~50: o alvo de amplitude (80 °C) fica inalcançável.

## Conclusões

1. A integração funciona: julho de 2040 é calculado, reaproveitado e mostrado no
   globo, com corte, horizonte e métodos auditáveis.
2. **Cientificamente, além de H1 a projeção LightGBM é pior que o sazonal**, e
   em horizontes de anos ela degenera. Os rankings de 2030–2040 são
   **exploratórios** e não devem ser lidos como previsão do mundo real.
3. Para décadas, seria preciso incorporar cenários climáticos externos
   regionalizados (ex.: Atlas do IPCC AR6) e medir a incerteza por variável e a
   estabilidade do ranking. O histórico de 92 meses não valida janelas de 120.

## Próximos passos sugeridos

- Avaliar `auto`/sazonal como padrão para horizontes > 1 mês, ou um híbrido
  (LightGBM H1 + sazonal depois), com o mesmo backtest.
- Restringir a projeção a limites físicos por variável (amplitude ≥ 0, NDVI e
  albedo em [0, 1]) e reavaliar.
- Imputar lags ausentes (ex.: sazonal do próprio ID) para conter a propagação
  de nulos, e reavaliar.

Referências: [estratégias diretas × recursivas (Taieb & Hyndman, 2014)](https://proceedings.mlr.press/v32/taieb14.html);
[Atlas do IPCC AR6](https://www.ipcc.ch/report/ar6/wg1/chapter/atlas/).
