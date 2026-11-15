"""Contrato de metadados dos artefatos de modelo."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    """Metadados de um artefato presente em ``models/``."""

    name: str = Field(..., description="Identificador lógico (caminho relativo sem extensão).")
    file: str = Field(..., description="Caminho relativo do artefato dentro de models/.")
    format: str = Field(..., description="Extensão/formato do artefato.", examples=["joblib"])
    description: str = Field(..., description="Descrição legível do modelo.")
    size_bytes: int = Field(..., description="Tamanho do artefato em bytes.")
    updated_at: datetime = Field(..., description="Data de modificação do arquivo (UTC).")
    tags: list[str] = Field(default_factory=list, description="Tags livres do sidecar.")
    algorithm: str | None = Field(default=None, description="Algoritmo declarado no sidecar.")
    framework: str | None = Field(default=None, description="Biblioteca/framework declarado.")
    target: str | None = Field(default=None, description="Variável-alvo declarada.")
    trained_at: str | None = Field(default=None, description="Data de treino declarada.")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Métricas do sidecar.")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Hiperparâmetros declarados no sidecar."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadados adicionais do sidecar."
    )


class ModelListResponse(BaseModel):
    """Lista de artefatos de modelo disponíveis."""

    items: list[ModelMetadata]
    total: int = Field(..., description="Quantidade de artefatos encontrados.")
