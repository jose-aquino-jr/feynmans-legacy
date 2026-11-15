"""Router de metadados dos artefatos de modelo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.dependencies import get_current_principal, get_model_repository
from app.schemas.common import error_responses
from app.schemas.model import ModelListResponse, ModelMetadata
from app.services.models import ModelRepository

ModelName = Annotated[
    str,
    Path(
        description="Nome lógico do artefato (caminho relativo sem extensão).",
        examples=["cluster_kmeans", "previsao/xgboost"],
    ),
]

router = APIRouter(
    prefix="/models",
    tags=["models"],
    dependencies=[Depends(get_current_principal)],
)


@router.get(
    "",
    response_model=ModelListResponse,
    summary="Lista artefatos de modelo",
    description=(
        "Varre `models/` e retorna os metadados dos artefatos encontrados. Nenhum "
        "artefato é carregado ou executado; sidecars `<nome>.meta.json` "
        "enriquecem a resposta."
    ),
    responses=error_responses(500),
)
def list_models(
    repository: Annotated[ModelRepository, Depends(get_model_repository)],
) -> ModelListResponse:
    return repository.list_models()


@router.get(
    "/{name:path}",
    response_model=ModelMetadata,
    summary="Metadados de um artefato de modelo",
    description="Retorna os metadados de um artefato específico presente em `models/`.",
    responses=error_responses(404, 500),
)
def get_model(
    name: ModelName,
    repository: Annotated[ModelRepository, Depends(get_model_repository)],
) -> ModelMetadata:
    return repository.get_model(name)
