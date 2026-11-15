"""Filtros e ordenação dos análogos por foco, utilidade e logística.

* **Foco** define o peso da logística na nota usada para ordenar
  (``nota_foco``): ``ciencia`` só olha o análogo, ``logistica`` só olha a
  logística e ``equilibrado`` é o custo-benefício (média geométrica).
* **Utilidade** troca a nota do análogo pela média dos nichos que importam
  para um tipo de campanha (ex.: rover usa terreno, poeira e operações).
* Os demais filtros recortam por qualidade, logística, país, região do globo,
  clima e tipo de base de apoio.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.services.errors import ApiError
from feynmans_legacy.vocabulario import UTILITIES


@dataclass(frozen=True)
class Foco:
    nome: str
    peso_logistica: float
    descricao: str


@dataclass(frozen=True)
class Utilidade:
    nome: str
    descricao: str
    nichos: tuple[str, ...]


FOCOS: dict[str, Foco] = {
    "ciencia": Foco("Ciência", 0.0, "Ordena só pela semelhança com a Lua ou Marte."),
    "equilibrado": Foco("Custo-benefício", 0.5,
                        "Média geométrica entre semelhança e logística."),
    "logistica": Foco("Logística", 1.0,
                      "Ordena pela proximidade dos EUA, do apoio e das rotas."),
}

UTILIDADES: dict[str, Utilidade] = {
    key: Utilidade(item["nome"], item["descricao"], tuple(item["nichos"]))
    for key, item in UTILITIES.items()
}

TIPOS = ("destaque", "geral", "especialista", "custo_beneficio")


@dataclass
class SiteFilters:
    """Recortes que dependem só do local terrestre."""

    destaque: bool | None = None
    eua: bool | None = None
    pais: str | None = None
    max_distancia_eua_km: float | None = None
    max_distancia_apoio_km: float | None = None
    min_apoios: int | None = None
    logistica_minima: float | None = None
    apoio_categoria: str | None = None
    apoio_vinculo: str | None = None
    lat_min: float | None = None
    lat_max: float | None = None
    lon_min: float | None = None
    lon_max: float | None = None
    temperatura_min: float | None = None
    temperatura_max: float | None = None

    def validate(self) -> None:
        for low, high, name in ((self.lat_min, self.lat_max, "lat"),
                                (self.lon_min, self.lon_max, "lon"),
                                (self.temperatura_min, self.temperatura_max, "temperatura")):
            if low is not None and high is not None and low > high:
                raise ApiError(400, "invalid_range",
                               f"{name}_min não pode ser maior que {name}_max.",
                               {"min": low, "max": high})


@dataclass
class PairFilters:
    """Recortes e ordenação de pares base ↔ local."""

    local: SiteFilters = field(default_factory=SiteFilters)
    tipo: str | None = None
    utilidade: str | None = None
    foco: str = "equilibrado"
    peso_logistica: float | None = None
    forte_em: list[str] = field(default_factory=list)
    evitar_fraco_em: list[str] = field(default_factory=list)
    nota_minima: float | None = None
    utilidade_minima: float | None = None
    foco_minimo: float | None = None

    @property
    def logistics_weight(self) -> float:
        return self.peso_logistica if self.peso_logistica is not None \
            else FOCOS[self.foco].peso_logistica

    def validate(self, known_niches: Iterable[str]) -> None:
        self.local.validate()
        if self.foco not in FOCOS:
            raise ApiError(400, "invalid_foco", f"Foco '{self.foco}' não existe.",
                           {"permitidos": sorted(FOCOS)})
        if self.utilidade is not None and self.utilidade not in UTILIDADES:
            raise ApiError(400, "invalid_utilidade",
                           f"Utilidade '{self.utilidade}' não existe.",
                           {"permitidos": sorted(UTILIDADES)})
        niches = set(known_niches)
        unknown = sorted(set(self.forte_em + self.evitar_fraco_em) - niches)
        if unknown:
            raise ApiError(400, "invalid_nicho", "Nicho desconhecido.",
                           {"nichos": unknown, "permitidos": sorted(niches)})


def split_values(values: Iterable[str] | None) -> list[str]:
    """Accept repeated query params and comma-separated values."""
    items: list[str] = []
    for value in values or []:
        items.extend(part.strip() for part in value.split(",") if part.strip())
    return items


def is_us(pais: pd.Series) -> pd.Series:
    return pais.fillna("").astype(str).str.startswith("Estados Unidos")


def sites_with_support(routes: pd.DataFrame | None, categoria: str | None,
                       vinculo: str | None) -> set[str] | None:
    """Locations whose main or alternative routes reach the requested support."""
    if categoria is None and vinculo is None:
        return None
    if routes is None:
        return set()
    mask = pd.Series(True, index=routes.index)
    if categoria is not None:
        mask &= routes["categoria"].astype(str).str.casefold().str.contains(
            categoria.casefold(), regex=False)
    if vinculo is not None:
        mask &= routes["vinculo"].astype(str).str.casefold() == vinculo.casefold()
    return set(routes.loc[mask, "location_id"].astype(str))


def site_mask(sites: pd.DataFrame, filters: SiteFilters,
              routes: pd.DataFrame | None, prefix: str = "") -> pd.Series:
    """Boolean mask over ``sites``; ``prefix`` names columns of a joined view."""

    def column(name: str) -> pd.Series:
        key = f"{prefix}{name}"
        if key in sites.columns:
            return sites[key]
        return pd.Series(np.nan, index=sites.index)

    mask = pd.Series(True, index=sites.index)
    if filters.destaque is not None:
        mask &= column("destaque").fillna(False).astype(bool) == filters.destaque
    if filters.eua is not None:
        mask &= is_us(column("pais")) == filters.eua
    if filters.pais is not None:
        mask &= column("pais").fillna("").astype(str).str.casefold() == filters.pais.casefold()
    bounds = (
        ("distancia_eua_km", None, filters.max_distancia_eua_km),
        ("distancia_apoio_km", None, filters.max_distancia_apoio_km),
        ("n_apoios_raio", filters.min_apoios, None),
        ("nota_logistica", filters.logistica_minima, None),
        ("latitude", filters.lat_min, filters.lat_max),
        ("temperatura_media_c", filters.temperatura_min, filters.temperatura_max),
    )
    for name, low, high in bounds:
        values = column(name)
        if low is not None:
            mask &= values >= low
        if high is not None:
            mask &= values <= high
    longitude = column("longitude")
    if filters.lon_min is not None:
        mask &= longitude >= filters.lon_min
    if filters.lon_max is not None:
        mask &= longitude <= filters.lon_max
    allowed = sites_with_support(routes, filters.apoio_categoria, filters.apoio_vinculo)
    if allowed is not None:
        mask &= sites["location_id"].astype(str).isin(allowed)
    return mask


def utility_scores(niche_scores: pd.DataFrame, utilidade: str) -> pd.Series:
    """Mean niche score (0–100) of each pair over the niches of one utility."""
    niches = UTILIDADES[utilidade].nichos
    chosen = niche_scores[niche_scores["nicho"].isin(niches)]
    return chosen.groupby("par_id")["nota"].mean()


def focus_score(science: pd.Series, logistics: pd.Series, weight: float) -> pd.Series:
    """Weighted geometric mean: 0 = only science, 1 = only logistics."""
    if weight <= 0:
        return science.astype(float)
    if weight >= 1:
        return logistics.astype(float)
    return (science.astype(float).clip(lower=0) ** (1 - weight)
            * logistics.astype(float).clip(lower=0) ** weight)


def has_any(values: pd.Series, wanted: Iterable[str]) -> pd.Series:
    targets = set(wanted)
    return values.fillna("").astype(str).map(
        lambda text: bool(targets & {item for item in text.split(",") if item}))


def pair_mask(view: pd.DataFrame, filters: PairFilters,
              routes: pd.DataFrame | None) -> pd.Series:
    """Mask over a pairs view joined with ``local_*`` site columns."""
    mask = site_mask(view, filters.local, routes, prefix="local_")
    if filters.tipo is not None:
        mask &= view["tipo"] == filters.tipo
    if filters.forte_em:
        mask &= has_any(view["pontos_fortes"], filters.forte_em) | has_any(
            view["nichos_destaque"], filters.forte_em)
    if filters.evitar_fraco_em:
        mask &= ~has_any(view["pontos_fracos"], filters.evitar_fraco_em)
    for name, low in (("nota_geral", filters.nota_minima),
                      ("nota_utilidade", filters.utilidade_minima),
                      ("nota_foco", filters.foco_minimo)):
        if low is not None:
            mask &= view[name] >= low
    return mask
