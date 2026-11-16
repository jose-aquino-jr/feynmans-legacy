"""Router dos análogos Terra ↔ Lua/Marte usados pelo mapa 3D."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.config import Settings
from app.dependencies import get_analog_repository, get_app_settings, get_current_principal
from app.schemas.analogos import (
    ApoioListResponse,
    BaseDetalhe,
    BaseListResponse,
    CustoBeneficioResponse,
    FiltrosResponse,
    LocalDetalhe,
    LocalListResponse,
    NichoListResponse,
    ParDetalhe,
)
from app.schemas.common import error_responses
from app.services.analog_filters import PairFilters, SiteFilters, split_values
from app.services.analogos import AnalogRepository

router = APIRouter(
    prefix="/analogos",
    tags=["analogos"],
    dependencies=[Depends(get_current_principal)],
)

Repository = Annotated[AnalogRepository, Depends(get_analog_repository)]
Corpo = Literal["lua", "marte"]
Foco = Literal["ciencia", "equilibrado", "logistica"]
Utilidade = Literal["habitat", "mobilidade", "geologia", "agua_recursos", "astrobiologia",
                    "clima_extremo", "tubos_lava"]
TipoPar = Literal["destaque", "geral", "especialista", "custo_beneficio"]


def site_filters(
    destaque: Annotated[bool | None, Query(description="Só locais padrão do software.")] = None,
    eua: Annotated[bool | None, Query(
        description="true: só locais nos EUA; false: só fora dos EUA.")] = None,
    pais: Annotated[str | None, Query(description="País do local terrestre.",
                                      examples=["México"])] = None,
    max_distancia_eua_km: Annotated[float | None, Query(
        ge=0, description="Distância máxima até uma instalação dos EUA.")] = None,
    max_distancia_apoio_km: Annotated[float | None, Query(
        ge=0, description="Distância máxima até a base de apoio principal.")] = None,
    min_apoios: Annotated[int | None, Query(
        ge=0, description="Mínimo de bases de apoio no raio (rotas alternativas).")] = None,
    logistica_minima: Annotated[float | None, Query(ge=0, le=100)] = None,
    apoio_categoria: Annotated[str | None, Query(
        description="Exige rota para uma base desta categoria (trecho do nome).",
        examples=["lançamento", "Espaço Profundo"])] = None,
    apoio_vinculo: Annotated[str | None, Query(
        description="Exige rota para uma base com este vínculo.",
        examples=["Nativa NASA"])] = None,
    lat_min: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lat_max: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon_min: Annotated[float | None, Query(ge=-180, le=180)] = None,
    lon_max: Annotated[float | None, Query(ge=-180, le=180)] = None,
    temperatura_min: Annotated[float | None, Query(
        description="Temperatura média mínima do local (°C).")] = None,
    temperatura_max: Annotated[float | None, Query(
        description="Temperatura média máxima do local (°C).")] = None,
) -> SiteFilters:
    return SiteFilters(
        destaque=destaque, eua=eua, pais=pais, max_distancia_eua_km=max_distancia_eua_km,
        max_distancia_apoio_km=max_distancia_apoio_km, min_apoios=min_apoios,
        logistica_minima=logistica_minima, apoio_categoria=apoio_categoria,
        apoio_vinculo=apoio_vinculo, lat_min=lat_min, lat_max=lat_max, lon_min=lon_min,
        lon_max=lon_max, temperatura_min=temperatura_min, temperatura_max=temperatura_max,
    )


def pair_filters(
    local: Annotated[SiteFilters, Depends(site_filters)],
    foco: Annotated[Foco, Query(
        description=("ciencia: só a semelhança; equilibrado: custo-benefício; "
                     "logistica: só EUA, apoio e rotas."))] = "equilibrado",
    peso_logistica: Annotated[float | None, Query(
        ge=0, le=1, description="Peso da logística em nota_foco; sobrepõe o foco.")] = None,
    utilidade: Annotated[Utilidade | None, Query(
        description="Troca a nota geral pela média dos nichos desta utilidade.")] = None,
    tipo: Annotated[TipoPar | None, Query(description="Motivo da relação.")] = None,
    forte_em: Annotated[list[str] | None, Query(
        description="Só pares fortes em algum destes nichos (repita ou separe por vírgula).",
        examples=["geologia,terreno"])] = None,
    evitar_fraco_em: Annotated[list[str] | None, Query(
        description="Remove pares fracos em algum destes nichos.",
        examples=["termico"])] = None,
    nota_minima: Annotated[float | None, Query(ge=0, le=100)] = None,
    utilidade_minima: Annotated[float | None, Query(ge=0, le=100)] = None,
    foco_minimo: Annotated[float | None, Query(ge=0, le=100)] = None,
) -> PairFilters:
    return PairFilters(
        local=local, tipo=tipo, utilidade=utilidade, foco=foco,
        peso_logistica=peso_logistica, forte_em=split_values(forte_em),
        evitar_fraco_em=split_values(evitar_fraco_em), nota_minima=nota_minima,
        utilidade_minima=utilidade_minima, foco_minimo=foco_minimo,
    )


Filters = Annotated[PairFilters, Depends(pair_filters)]
Sites = Annotated[SiteFilters, Depends(site_filters)]
LimitQuery = Annotated[int | None, Query(ge=1)]
OffsetQuery = Annotated[int, Query(ge=0)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def _limit(limit: int | None, settings: Settings) -> int:
    return min(limit or settings.default_limit, settings.max_limit)


@router.get(
    "/filtros",
    response_model=FiltrosResponse,
    summary="Opções dos filtros",
    description="Focos, utilidades, nichos, países e tipos de base de apoio aceitos.",
    responses=error_responses(404, 500),
)
def filter_options(repository: Repository) -> FiltrosResponse:
    return repository.filter_options()


@router.get(
    "/nichos",
    response_model=NichoListResponse,
    summary="Lista os nichos de comparação",
    description="Identificador, nome legível e corpos (Lua/Marte) de cada nicho.",
    responses=error_responses(404, 500),
)
def list_niches(repository: Repository) -> NichoListResponse:
    return repository.list_niches()


@router.get(
    "/bases",
    response_model=BaseListResponse,
    summary="Lista as bases da Lua e de Marte",
    description="Bases de referência com o ponto no globo e o melhor análogo terrestre.",
    responses=error_responses(400, 404, 500),
)
def list_bases(
    repository: Repository,
    corpo: Annotated[Corpo | None, Query(description="Filtra por corpo.")] = None,
) -> BaseListResponse:
    return repository.list_bases(corpo)


@router.get(
    "/bases/{base_id}",
    response_model=BaseDetalhe,
    summary="Locais terrestres relacionados a uma base",
    description=(
        "Retorna a base e os pares com o local terrestre embutido. Aceita os mesmos "
        "filtros de `/analogos/pares`. `ordenar`: `nota` (rank_base, padrão), "
        "`custo_beneficio` ou `foco` (nota_foco, segue `foco`, `peso_logistica` e "
        "`utilidade`)."
    ),
    responses=error_responses(400, 404, 500),
)
def get_base(
    repository: Repository,
    settings: SettingsDep,
    filters: Filters,
    base_id: Annotated[str, Path(examples=["MARTE_JEZERO"])],
    ordenar: Annotated[Literal["nota", "custo_beneficio", "foco"], Query()] = "nota",
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> BaseDetalhe:
    return repository.get_base(base_id, filters, ordenar=ordenar,
                               limit=_limit(limit, settings), offset=offset)


@router.get(
    "/pares",
    response_model=CustoBeneficioResponse,
    summary="Busca de pares por foco, utilidade e logística",
    description=(
        "Lista pares de todas as bases ordenados por `nota_foco` (maior primeiro). O "
        "foco define o peso da logística: `ciencia` = 0, `equilibrado` = 0,5, "
        "`logistica` = 1 (ou use `peso_logistica`). Com `utilidade`, a nota da "
        "semelhança vira a média dos nichos daquela utilidade. Valores aceitos em "
        "`/analogos/filtros`."
    ),
    responses=error_responses(400, 404, 500),
)
def list_pairs(
    repository: Repository,
    settings: SettingsDep,
    filters: Filters,
    corpo: Annotated[Corpo | None, Query()] = None,
    base_id: Annotated[str | None, Query(examples=["MARTE_GALE"])] = None,
    apenas_top: Annotated[bool, Query(
        description="Só os melhores custo-benefício de cada base.")] = False,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> CustoBeneficioResponse:
    return repository.list_pairs(filters, corpo=corpo, base_id=base_id,
                                 apenas_top=apenas_top, limit=_limit(limit, settings),
                                 offset=offset)


@router.get(
    "/custo-beneficio",
    response_model=CustoBeneficioResponse,
    summary="Melhores análogos em custo-benefício",
    description=(
        "Atalho de `/analogos/pares` com `apenas_top=true`: os melhores custo-benefício "
        "de cada base, com local, base espacial e rotas de apoio. Aceita os mesmos "
        "filtros (foco, utilidade, EUA, distância, tipo de apoio, região, clima)."
    ),
    responses=error_responses(400, 404, 500),
)
def list_cost_benefit(
    repository: Repository,
    settings: SettingsDep,
    filters: Filters,
    corpo: Annotated[Corpo | None, Query()] = None,
    base_id: Annotated[str | None, Query(examples=["MARTE_GALE"])] = None,
    apenas_top: Annotated[bool, Query(
        description="Só os melhores custo-benefício de cada base (padrão).")] = True,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> CustoBeneficioResponse:
    return repository.list_pairs(filters, corpo=corpo, base_id=base_id,
                                 apenas_top=apenas_top, limit=_limit(limit, settings),
                                 offset=offset)


@router.get(
    "/locais",
    response_model=LocalListResponse,
    summary="Lista os locais terrestres com análogos",
    description=(
        "Filtra por destaque, EUA, país, logística, tipo de base de apoio, região "
        "(`lat_*`, `lon_*`) e temperatura. `base_id` restringe aos locais "
        "relacionados a uma base. `ordenar`: `padrao` (destaques primeiro), `nota`, "
        "`custo_beneficio` ou `logistica`."
    ),
    responses=error_responses(400, 404, 500),
)
def list_sites(
    repository: Repository,
    settings: SettingsDep,
    filters: Sites,
    base_id: Annotated[str | None, Query(examples=["LUA_POLO_SUL"])] = None,
    ordenar: Annotated[Literal["padrao", "nota", "custo_beneficio", "logistica"],
                       Query()] = "padrao",
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> LocalListResponse:
    return repository.list_sites(filters, base_id=base_id, ordenar=ordenar,
                                 limit=_limit(limit, settings), offset=offset)


@router.get(
    "/locais/{location_id}",
    response_model=LocalDetalhe,
    summary="Bases da Lua e de Marte relacionadas a um local terrestre",
    responses=error_responses(404, 500),
)
def get_site(
    repository: Repository,
    location_id: Annotated[str, Path(examples=["T042068"])],
) -> LocalDetalhe:
    return repository.get_site(location_id)


@router.get(
    "/pares/{par_id}",
    response_model=ParDetalhe,
    summary="Detalhe de um par com a série mensal da nota",
    description=(
        "Inclui a nota geral nos meses observados e nos meses previstos pelo modelo "
        "LightGBM (`origem = prevista`) e as rotas de apoio do local."
    ),
    responses=error_responses(404, 500),
)
def get_pair(
    repository: Repository,
    par_id: Annotated[str, Path(examples=["MARTE_JEZERO__T042068"])],
) -> ParDetalhe:
    return repository.get_pair(par_id)


@router.get(
    "/apoios",
    response_model=ApoioListResponse,
    summary="Bases de apoio da NASA e parceiros",
    description="Catálogo usado na logística (sem a geometria WKB), para marcar no globo.",
    responses=error_responses(400, 404, 500),
)
def list_support(
    repository: Repository,
    eua: Annotated[bool | None, Query(description="Só instalações nos EUA.")] = None,
    usado: Annotated[bool | None, Query(
        description="Só as bases usadas no cálculo (sem vínculo restrito ou oceano).")] = None,
    categoria: Annotated[str | None, Query(examples=["Centro de campo NASA"])] = None,
) -> ApoioListResponse:
    return repository.list_support(eua=eua, usado=usado, categoria=categoria)
