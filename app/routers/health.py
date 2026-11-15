"""Router de saúde da aplicação."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.config import Settings
from app.dependencies import get_app_settings
from app.schemas.common import error_responses
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Status da aplicação",
    description="Retorna o estado básico da API e a disponibilidade dos diretórios de dados.",
    responses=error_responses(500),
)
def health(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    """Health check sem tocar nos arquivos de dados."""
    started_at = float(getattr(request.app.state, "started_at", time.perf_counter()))
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.perf_counter() - started_at, 3),
        data_dir=str(settings.data_dir),
        data_dir_exists=settings.data_dir.is_dir(),
        models_dir=str(settings.models_dir),
        models_dir_exists=settings.models_dir.is_dir(),
    )
