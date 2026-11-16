"""Rotas das recomendações temporais: top K por base para um ano/mês."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.dependencies import get_current_principal, get_recommendation_service
from app.schemas.common import error_responses
from app.schemas.recommendations import (
    Calculando,
    Corpo,
    Estrategia,
    OpcoesResponse,
    RecomendacoesResponse,
)
from app.services.recommendations import RecommendationService

router = APIRouter(
    prefix="/analogos/recomendacoes",
    tags=["recomendacoes"],
    dependencies=[Depends(get_current_principal)],
)

Service = Annotated[RecommendationService, Depends(get_recommendation_service)]


@router.get(
    "/opcoes",
    response_model=OpcoesResponse,
    summary="Bases, nichos, meses observados e publicação",
    responses=error_responses(503),
)
def options(service: Service) -> OpcoesResponse:
    return service.options()


@router.get(
    "",
    response_model=RecomendacoesResponse,
    summary="Top K locais terrestres por base para um AAAAMM",
    description=(
        "Mês observado → dados reais do mês. Mês futuro → `estrategia=recursiva` "
        "(projeção LightGBM estendida mês a mês; padrão do front), `auto` (legado: "
        "direto até H3 e cenário sazonal depois) ou `sazonal`. Se a projeção ainda "
        "não chegou ao mês, responde **202** com `Retry-After`; repita a mesma URL. "
        "Os alvos de cada base são fixos; só o estado da Terra muda com o mês."
    ),
    responses={
        202: {"model": Calculando, "description": "Projeção em andamento."},
        **error_responses(400, 404, 500, 503),
    },
)
def recommendations(
    service: Service,
    response: Response,
    anomes: Annotated[int, Query(ge=100001, le=999912, examples=[204007])],
    nicho: Annotated[str, Query(examples=["Todos", "termico"])] = "Todos",
    base_id: Annotated[str | None, Query(examples=["MARTE_JEZERO"])] = None,
    corpo: Annotated[Corpo | None, Query()] = None,
    k: Annotated[int, Query(ge=1, le=1000)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    cobertura_minima: Annotated[float, Query(gt=0, le=1)] = 0.7,
    estrategia: Annotated[Estrategia, Query()] = "auto",
) -> Any:
    result = service.recommend(
        anomes=anomes, niche=nicho, base_id=base_id, body=corpo,
        k=min(k, service.settings.recomendacoes_k_max), offset=offset,
        coverage=cobertura_minima, strategy=estrategia)
    if isinstance(result, Calculando):
        return JSONResponse(
            status_code=202, content=result.model_dump(mode="json"),
            headers={"Retry-After": str(result.repetir_em_segundos)})
    response.headers["X-Origem-Estado"] = result.origem
    return result


@router.get(
    "/tarefas",
    summary="Estado das projeções em andamento ou recentes",
    include_in_schema=True,
)
def jobs(service: Service) -> dict[str, Any]:
    return {"tarefas": service.job_states()}
