"""Explicações em texto das escolhas de análogos, geradas a partir das notas.

Os textos não trazem nenhuma informação além das tabelas: motivo da escolha
(``tipo``), nichos mais e menos parecidos com exemplos de variáveis (valor na
Terra × alvo), cobertura de dados, logística e tendência prevista pelo modelo.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .vocabulario import UTILITIES, niche_label

STRONG = 75.0
WEAK = 50.0
STABLE_DELTA = 2.0
MIN_USE_SCORE = 70.0
MIN_UTILITY_NICHES = 2


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _number(value: Any) -> float | None:
    return None if _missing(value) else float(value)


def fmt(value: float, digits: int = 1) -> str:
    """Number in pt-BR style: 1.234,5."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_score(value: Any) -> str:
    return "—" if _missing(value) else fmt(float(value), 0)


def fmt_value(value: float) -> str:
    size = abs(value)
    digits = 0 if size >= 100 else 1 if size >= 10 else 2
    return fmt(value, digits)


def logistics_quality(score: float) -> str:
    if score >= 80:
        return "excelente"
    if score >= 60:
        return "boa"
    if score >= 40:
        return "regular"
    return "fraca"


def join_pt(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


def variable_phrase(row: Mapping[str, Any]) -> str:
    """'temperatura média do ar: 28,2 °C aqui contra -46,3 °C no alvo'."""
    name, unit = str(row["nome"]), str(row["unidade"])
    value, target = row["valor_terra"], row["alvo"]
    if unit == "0/1":
        here = "presente" if float(value) >= 0.5 else "ausente"
        there = "presente" if float(target) >= 0.5 else "ausente"
        return f"{name} {here} aqui e {there} no alvo"
    suffix = f" {unit}" if unit else ""
    where = ("no alvo (equivalente terrestre)"
             if row.get("tipo_alvo") == "equivalente terrestre" else "no alvo")
    return (f"{name}: {fmt_value(float(value))}{suffix} aqui contra "
            f"{fmt_value(float(target))}{suffix} {where}")


def _known(variables: pd.DataFrame) -> pd.DataFrame:
    return variables.dropna(subset=["valor_terra", "nota"])


def best_example(variables: pd.DataFrame, niche: str) -> str | None:
    """Best-matching variable, skipping uninformative 0-vs-0 comparisons."""
    rows = _known(variables[variables["nicho"] == niche])
    informative = rows[(rows["valor_terra"].abs() > 1e-9) | (rows["alvo"].abs() > 1e-9)]
    if informative.empty:
        return None
    return variable_phrase(informative.sort_values("nota", ascending=False).iloc[0])


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def worst_example(variables: pd.DataFrame, niche: str) -> str | None:
    rows = _known(variables[variables["nicho"] == niche])
    if rows.empty:
        return None
    return variable_phrase(rows.sort_values("nota").iloc[0])


TREND_TEXT = {"estável": ("tende a ficar estável", "Previsão estável"),
              "alta": ("tende a subir", "Previsão em alta"),
              "queda": ("tende a cair", "Previsão em queda")}


def trend_state(observed: float, forecast: float) -> str:
    delta = forecast - observed
    if abs(delta) < STABLE_DELTA:
        return "estável"
    return "alta" if delta > 0 else "queda"


def explain_pair(
    pair: Mapping[str, Any],
    base_name: str,
    site: Mapping[str, Any],
    niche_scores: Mapping[str, float],
    variables: pd.DataFrame,
    trend: tuple[float, float] | None,
    raio_km: float,
) -> tuple[str, list[str]]:
    """Paragraph and short reasons for one base ↔ site pair."""
    score = pair.get("nota_geral")
    score_text = (f"nota geral {fmt_score(score)}" if not _missing(score)
                  else "sem nota geral (dados insuficientes no perfil completo)")
    kind = str(pair.get("tipo"))
    chosen = [item for item in str(pair.get("nichos_destaque") or "").split(",") if item]
    logistics = pair.get("nota_logistica")
    sentences: list[str] = []
    reasons: list[str] = []

    if kind == "destaque":
        sentences.append(f"{site['nome']} é um dos locais padrão do software; com "
                         f"{base_name} tem {score_text}.")
        reasons.append("Local padrão")
    elif kind == "geral":
        sentences.append(f"Está entre as melhores notas gerais para {base_name}: "
                         f"{pair.get('rank_base')}º lugar, {score_text}.")
        reasons.append(f"Top {pair.get('rank_base')} em semelhança")
    elif kind == "especialista":
        labels = [f"{niche_label(n)} ({fmt_score(niche_scores.get(n))})" for n in chosen]
        sentences.append(f"Foi escolhido por ser muito parecido em {join_pt(labels)}, "
                         f"mesmo com {score_text}.")
        reasons.extend(f"Especialista em {niche_label(n)}" for n in chosen[:2])
    else:
        sentences.append(f"Está entre os melhores custo-benefício para {base_name}: "
                         f"{score_text} e logística {fmt_score(logistics)}.")
        reasons.append("Melhor custo-benefício")

    known = {n: float(v) for n, v in niche_scores.items() if not _missing(v)}
    skip = set(chosen) if kind == "especialista" else set()
    strong = sorted((n for n, v in known.items() if v >= STRONG and n not in skip),
                    key=lambda n: -known[n])[:3]
    weak = sorted((n for n, v in known.items() if v < WEAK), key=lambda n: known[n])[:2]
    if strong:
        labels = [f"{niche_label(n)} ({fmt_score(known[n])})" for n in strong]
        lead = "Também parecido em" if skip else "Parecido em"
        sentence = f"{lead} {join_pt(labels)}."
        example = best_example(variables, strong[0])
        if example:
            sentence += f" Exemplo: {example}."
        sentences.append(sentence)
        reasons.extend(f"Forte em {niche_label(n)} ({fmt_score(known[n])})" for n in strong[:2])
    if weak:
        parts = []
        for niche in weak:
            example = worst_example(variables, niche)
            label = f"{niche_label(niche)} ({fmt_score(known[niche])})"
            parts.append(f"{label}, porque {example}" if example else label)
        sentences.append(f"Diferente em {'; '.join(parts)}.")
        reasons.extend(f"Fraco em {niche_label(n)} ({fmt_score(known[n])})" for n in weak)
    elif known:
        sentences.append("Nenhum nicho fica abaixo de 50.")

    coverage = _number(pair.get("cobertura"))
    if coverage is not None and coverage < 0.999:
        missing = variables[variables["valor_terra"].isna()]["nome"].drop_duplicates()
        names = join_pt(list(missing.head(3)))
        sentences.append(f"Faltam dados de {names} neste local; a nota usa "
                         f"{fmt(coverage * 100, 0)}% do perfil.")
        reasons.append("Dados parciais")

    logistics_score = _number(logistics)
    if logistics_score is not None:
        quality = logistics_quality(logistics_score)
        details = []
        if not _missing(site.get("distancia_eua_km")):
            details.append(f"{fmt(float(site['distancia_eua_km']), 0)} km da instalação "
                           "dos EUA mais próxima")
        if site.get("apoio_principal_nome") and not _missing(site.get("distancia_apoio_km")):
            details.append(f"apoio principal em {site['apoio_principal_nome']}, a "
                           f"{fmt(float(site['distancia_apoio_km']), 0)} km")
        if not _missing(site.get("n_apoios_raio")):
            count = plural(int(site["n_apoios_raio"]), "base de apoio", "bases de apoio")
            details.append(f"{count} a até {fmt(raio_km, 0)} km")
        sentence = f"Logística {quality} ({fmt_score(logistics)})"
        sentences.append(sentence + (": " + "; ".join(details) if details else "") + ".")
        cost_benefit = pair.get("custo_beneficio")
        if not _missing(cost_benefit):
            sentences.append(f"Custo-benefício {fmt_score(cost_benefit)}.")
        reasons.append(f"Logística {quality}")

    if trend is not None:
        text, reason = TREND_TEXT[trend_state(*trend)]
        sentences.append(f"Pela previsão do modelo, a nota {text} nos próximos meses "
                         f"({fmt_score(trend[0])} → {fmt_score(trend[1])}).")
        reasons.append(reason)
    return " ".join(sentences), reasons


def utility_scores(niche_scores: Mapping[str, float]) -> dict[str, float]:
    """Mean niche score of each utility; needs at least two niches with data."""
    scores = {}
    for key, utility in UTILITIES.items():
        values = [float(niche_scores[n]) for n in utility["nichos"]
                  if n in niche_scores and not _missing(niche_scores[n])]
        if len(values) >= MIN_UTILITY_NICHES:
            scores[key] = sum(values) / len(values)
    return scores


def explain_site(
    site: Mapping[str, Any],
    pairs: pd.DataFrame,
    base_names: Mapping[str, str],
    best_uses: Sequence[tuple[str, float]],
    raio_km: float,
) -> str:
    """Summary of one Earth site across the bases it is related to."""
    sentences = [f"Relacionado a {plural(len(pairs), 'base', 'bases')} da Lua e de Marte."]
    scored = pairs.dropna(subset=["nota_geral"])
    if not scored.empty:
        best = scored.sort_values("nota_geral", ascending=False).iloc[0]
        sentences.append(f"Mais parecido com {base_names[best['base_id']]} "
                         f"(nota {fmt_score(best['nota_geral'])}).")
    if "custo_beneficio" in pairs.columns:
        valued = pairs.dropna(subset=["custo_beneficio"])
        if not valued.empty:
            best = valued.sort_values("custo_beneficio", ascending=False).iloc[0]
            sentences.append(f"Melhor custo-benefício com {base_names[best['base_id']]} "
                             f"({fmt_score(best['custo_beneficio'])}).")
    if best_uses:
        labels = [f"{UTILITIES[key]['nome']} ({fmt_score(score)})" for key, score in best_uses]
        sentences.append(f"Mais útil para {join_pt(labels)}.")
    if not _missing(site.get("nota_logistica")):
        logistics = float(site["nota_logistica"])
        sentence = f"Logística {logistics_quality(logistics)} ({fmt_score(logistics)})"
        if site.get("apoio_principal_nome") and not _missing(site.get("distancia_apoio_km")):
            sentence += (f", com apoio principal em {site['apoio_principal_nome']} a "
                         f"{fmt(float(site['distancia_apoio_km']), 0)} km")
        if not _missing(site.get("n_apoios_raio")):
            count = plural(int(site["n_apoios_raio"]), "base", "bases")
            sentence += f" e {count} a até {fmt(raio_km, 0)} km"
        sentences.append(sentence + ".")
    climate = []
    if not _missing(site.get("temperatura_media_c")):
        climate.append(f"{fmt(float(site['temperatura_media_c']), 1)} °C de média")
    if not _missing(site.get("precipitacao_mm_dia")):
        climate.append(f"{fmt(float(site['precipitacao_mm_dia']), 2)} mm/dia de chuva")
    if not _missing(site.get("elevacao_media_m")):
        climate.append(f"{fmt(float(site['elevacao_media_m']), 0)} m de altitude")
    if climate:
        sentences.append(f"Clima e relevo: {join_pt(climate)}.")
    return " ".join(sentences)


def explain_base(base: Mapping[str, Any], niche_medians: pd.Series,
                 site_names: Mapping[str, str]) -> str:
    """Summary of one Moon/Mars base and what Earth reproduces well or badly."""
    sentences = [f"{base['nome']}: {int(base['n_pares'])} análogos na Terra."]
    if base.get("melhor_location_id") and not _missing(base.get("melhor_nota")):
        sentences.append(f"Mais parecido: {site_names[base['melhor_location_id']]} "
                         f"(nota {fmt_score(base['melhor_nota'])}).")
    best_value = base.get("melhor_custo_beneficio_location_id")
    if best_value and not _missing(base.get("melhor_custo_beneficio")):
        sentences.append(f"Melhor custo-benefício: {site_names[best_value]} "
                         f"({fmt_score(base['melhor_custo_beneficio'])}).")
    medians = niche_medians.dropna().sort_values(ascending=False)
    easy = [f"{niche_label(n)} ({fmt_score(v)})"
            for n, v in medians[medians >= WEAK].head(3).items()]
    hard = [f"{niche_label(n)} ({fmt_score(v)})"
            for n, v in medians[medians < WEAK].sort_values().head(2).items()]
    if easy:
        sentences.append(f"Na Terra é mais fácil reproduzir {join_pt(easy)}.")
    if hard:
        sentences.append(f"O mais difícil é {join_pt(hard)}.")
    if easy or hard:
        sentences[-1] = sentences[-1][:-1] + " (mediana entre os análogos)."
    return " ".join(sentences)


def add_explanations(tables: dict[str, pd.DataFrame], raio_rotas_km: float = 2500.0) -> None:
    """Add ``explicacao``/``motivos`` to pairs and ``explicacao`` to sites and bases."""
    radius = raio_rotas_km
    pairs, sites, bases = tables["pares"], tables["locais"], tables["bases"]
    niches = tables["pares_nichos"]
    variables = tables.get("pares_variaveis", pd.DataFrame(
        columns=["par_id", "nicho", "nome", "unidade", "valor_terra", "alvo", "nota"]))
    series = tables.get("series")
    base_names = dict(zip(bases["base_id"], bases["nome"], strict=True))
    site_names = dict(zip(sites["location_id"], sites["nome"], strict=True))
    site_rows = sites.set_index("location_id")
    by_pair = {key: dict(zip(group["nicho"], group["nota"], strict=True))
               for key, group in niches.groupby("par_id")}
    variables_by_pair = dict(tuple(variables.groupby("par_id")))
    trends: dict[str, tuple[float, float]] = {}
    if series is not None and not series.empty:
        for key, group in series.dropna(subset=["nota"]).groupby("par_id"):
            seen = group[group["origem"] == "observada"].sort_values("anomes")
            ahead = group[group["origem"] == "prevista"].sort_values("anomes")
            if not seen.empty and not ahead.empty:
                trends[str(key)] = (float(seen["nota"].iloc[-1]), float(ahead["nota"].iloc[-1]))

    texts, reasons = [], []
    empty = variables.iloc[0:0]
    for pair in pairs.to_dict("records"):
        text, items = explain_pair(
            pair, base_names[pair["base_id"]], site_rows.loc[pair["location_id"]].to_dict()
            | {"nome": site_names[pair["location_id"]]},
            by_pair.get(pair["par_id"], {}), variables_by_pair.get(pair["par_id"], empty),
            trends.get(pair["par_id"]), radius)
        texts.append(text)
        reasons.append("\n".join(items))
    pairs["explicacao"] = texts
    pairs["motivos"] = reasons

    site_texts, site_uses = [], []
    for site in sites.to_dict("records"):
        related = pairs[pairs["location_id"] == site["location_id"]]
        uses: dict[str, float] = {}
        for pair_id in related["par_id"]:
            for key, value in utility_scores(by_pair.get(pair_id, {})).items():
                uses[key] = max(uses.get(key, 0.0), value)
        best_uses = sorted(((k, v) for k, v in uses.items() if v >= MIN_USE_SCORE),
                           key=lambda item: -item[1])[:2]
        site_uses.append(",".join(key for key, _ in best_uses))
        site_texts.append(explain_site(site, related, base_names, best_uses, radius))
    sites["explicacao"] = site_texts
    sites["usos_recomendados"] = site_uses

    base_texts = []
    for base in bases.to_dict("records"):
        medians = niches[niches["base_id"] == base["base_id"]].groupby("nicho")["nota"].median()
        base_texts.append(explain_base(base, medians, site_names))
    bases["explicacao"] = base_texts
