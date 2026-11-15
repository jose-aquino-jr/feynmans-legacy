# Bases de apoio

`nasa_bases_suporte.parquet` (GeoParquet, 182 linhas) lista instalações da NASA,
de agências parceiras, de contratadas e de apoio a campanhas: centros de campo,
redes DSN/NSN/TDRS, sítios de lançamento, bases de balões e apoio logístico.

| Coluna | Uso na logística |
|--------|------------------|
| `id`, `nome`, `categoria`, `operador`, `pais` | identificação e exibição |
| `lat`, `lon` | distância até os locais terrestres |
| `prioridade_combinada` (0–1) | peso da base na nota de apoio e nas rotas |
| `vinculo` | `Restrita` fica fora do cálculo |
| `continente` | `Oceano` (zonas de amerissagem) fica fora do cálculo |

Fonte declarada no arquivo: compilação de fontes públicas (NASA, ESA ESTRACK,
JAXA, ILRS/IVS, Wikipedia), data de referência 2026-11-15. A coluna
`coord_precisao` indica que algumas posições são aproximadas (cidade ou
centroide).

Usado por `src/feynmans_legacy/logistics.py` e publicado em
`data/tratados/analogos/apoios.parquet` sem a geometria WKB.
