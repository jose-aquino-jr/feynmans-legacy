"""Schemas do endpoint de saúde."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Estado da aplicação e disponibilidade dos diretórios de dados."""

    status: Literal["ok"] = Field(default="ok", examples=["ok"])
    app: str = Field(..., description="Nome da aplicação.")
    version: str = Field(..., description="Versão da API.")
    environment: str = Field(..., description="Ambiente de execução.")
    uptime_seconds: float = Field(..., description="Tempo desde a inicialização, em segundos.")
    data_dir: str = Field(..., description="Diretório de datasets processados.")
    data_dir_exists: bool = Field(..., description="Se o diretório de dados existe.")
    models_dir: str = Field(..., description="Diretório de artefatos de modelo.")
    models_dir_exists: bool = Field(..., description="Se o diretório de modelos existe.")
