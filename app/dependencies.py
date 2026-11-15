"""Dependências FastAPI e ponto de extensão para autenticação."""

from __future__ import annotations

from typing import Any, cast

from fastapi import Request

from app.config import Settings
from app.services.datasets import DatasetRepository
from app.services.models import ModelRepository


def get_app_settings(request: Request) -> Settings:
    """Recupera a configuração associada ao app em execução."""
    return cast(Settings, request.app.state.settings)


def get_dataset_repository(request: Request) -> DatasetRepository:
    """Recupera o repositório de datasets (um por instância de app)."""
    return cast(DatasetRepository, request.app.state.dataset_repository)


def get_model_repository(request: Request) -> ModelRepository:
    """Recupera o repositório de modelos (um por instância de app)."""
    return cast(ModelRepository, request.app.state.model_repository)


async def get_current_principal() -> dict[str, Any] | None:
    """Ponto de extensão de autenticação.

    Hoje a API é somente leitura e pública; este dependency existe para que a
    autenticação possa ser adicionada sem alterar as assinaturas das rotas.
    Substitua o retorno por um usuário/serviço real quando necessário.
    """
    return None
