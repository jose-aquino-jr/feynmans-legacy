"""Router dos análogos Terra ↔ Lua/Marte usados pelo mapa 3D."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.config import Settings
from app.dependencies import get_analog_repository, get_app_settings, get_current_principal
from app.schemas.analogos import (
    BaseDetalhe,
    BaseListResponse,
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
    tipo: Annotated[Literal["destaque", "geral", "especialista"] | None,
                    Query(description="Filtra pelo motivo da relação.")] = None,
    destaque: Annotated[bool | None, Query(description="Só locais padrão.")] = None,
    forte_em: Annotated[str | None, Query(
        description="Só pares fortes neste nicho (ex.: termico, geologia, terreno).",
        examples=["geologia"])] = None,
    nota_minima: Annotated[float | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> BaseDetalhe:
    return repository.get_base(
        base_id, tipo=tipo, destaque=destaque, forte_em=forte_em,
        nota_minima=nota_minima, limit=min(limit or settings.default_limit, settings.max_limit),
    )


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
