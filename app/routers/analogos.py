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
    LocalDetalhe,
    LocalListResponse,
    NichoListResponse,
    ParDetalhe,
)
from app.schemas.common import error_responses
from app.services.analogos import AnalogRepository

router = APIRouter(
    prefix="/analogos",
    tags=["analogos"],
    dependencies=[Depends(get_current_principal)],
)

Repository = Annotated[AnalogRepository, Depends(get_analog_repository)]


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
    corpo: Annotated[Literal["lua", "marte"] | None,
                     Query(description="Filtra por corpo.")] = None,
) -> BaseListResponse:
    return repository.list_bases(corpo)


@router.get(
    "/bases/{base_id}",
    response_model=BaseDetalhe,
    summary="Locais terrestres relacionados a uma base",
    description=(
        "Retorna a base e os pares com o local terrestre embutido (nome, coordenadas, "
        "raio), a nota geral, a nota por nicho e os pontos fortes e fracos. Ordem: "
        "`rank_base` (melhor nota geral primeiro)."
    ),
    responses=error_responses(400, 404, 500),
)
def get_base(
    repository: Repository,
    settings: Annotated[Settings, Depends(get_app_settings)],
    base_id: Annotated[str, Path(examples=["MARTE_JEZERO"])],
    tipo: Annotated[Literal["destaque", "geral", "especialista", "custo_beneficio"] | None,
                    Query(description="Filtra pelo motivo da relação.")] = None,
    destaque: Annotated[bool | None, Query(description="Só locais padrão.")] = None,
    forte_em: Annotated[str | None, Query(
        description="Só pares fortes neste nicho (ex.: termico, geologia, terreno).",
        examples=["geologia"])] = None,
    nota_minima: Annotated[float | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
    ordenar: Annotated[Literal["nota", "custo_beneficio"], Query(
        description="nota (rank_base) ou custo_beneficio (maior primeiro).")] = "nota",
) -> BaseDetalhe:
    return repository.get_base(
        base_id, tipo=tipo, destaque=destaque, forte_em=forte_em,
        nota_minima=nota_minima, limit=min(limit or settings.default_limit, settings.max_limit),
        ordenar=ordenar,
    )


@router.get(
    "/custo-beneficio",
    response_model=CustoBeneficioResponse,
    summary="Melhores análogos em custo-benefício",
    description=(
        "Pares ordenados por `custo_beneficio = raiz(nota_geral × nota_logistica)`. A "
        "logística mede a proximidade dos EUA, da melhor base de apoio da NASA/parceiros "
        "e a quantidade de bases no raio (rotas alternativas). Cada item traz o local, a "
        "base espacial e as rotas: a base de apoio principal e as alternativas."
    ),
    responses=error_responses(400, 404, 500),
)
def list_cost_benefit(
    repository: Repository,
    settings: Annotated[Settings, Depends(get_app_settings)],
    corpo: Annotated[Literal["lua", "marte"] | None, Query()] = None,
    base_id: Annotated[str | None, Query(examples=["MARTE_GALE"])] = None,
    apenas_top: Annotated[bool, Query(
        description="Só os melhores custo-benefício de cada base (padrão).")] = True,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> CustoBeneficioResponse:
    return repository.list_cost_benefit(
        corpo=corpo, base_id=base_id, apenas_top=apenas_top,
        limit=min(limit or settings.default_limit, settings.max_limit),
    )


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


@router.get(
    "/locais",
    response_model=LocalListResponse,
    summary="Lista os locais terrestres com análogos",
    description="Locais padrão (`destaque=true`) primeiro, depois pela melhor nota.",
    responses=error_responses(400, 404, 500),
)
def list_sites(
    repository: Repository,
    settings: Annotated[Settings, Depends(get_app_settings)],
    destaque: Annotated[bool | None, Query(description="Só locais padrão.")] = None,
    pais: Annotated[str | None, Query(examples=["Sudão"])] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocalListResponse:
    return repository.list_sites(
        destaque=destaque, pais=pais,
        limit=min(limit or settings.default_limit, settings.max_limit), offset=offset,
    )


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
        "LightGBM (`origem = prevista`)."
    ),
    responses=error_responses(404, 500),
)
def get_pair(
    repository: Repository,
    par_id: Annotated[str, Path(examples=["MARTE_JEZERO__T042068"])],
) -> ParDetalhe:
    return repository.get_pair(par_id)
