"""Contrato de datasets, registros e agregações."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    """Metadados de uma coluna do dataset."""

    name: str = Field(..., description="Nome da coluna.", examples=["score"])
    dtype: str = Field(..., description="Tipo inferido/armazenado.", examples=["double"])
    description: str | None = Field(
        default=None,
        description="Descrição opcional vinda do sidecar ``<dataset>.meta.json``.",
    )


class DatasetMetadata(BaseModel):
    """Metadados completos de um dataset."""

    name: str = Field(..., description="Identificador lógico (caminho relativo sem extensão).")
    file: str = Field(..., description="Caminho relativo do arquivo dentro de data/tratados.")
    format: Literal["csv", "parquet"] = Field(..., description="Formato físico do arquivo.")
    description: str = Field(..., description="Descrição legível do dataset.")
    columns: list[ColumnMetadata] = Field(
        default_factory=list, description="Colunas disponíveis para filtros/projeção."
    )
    row_count: int | None = Field(
        default=None, description="Número de registros; ``null`` quando o arquivo não é legível."
    )
    updated_at: datetime = Field(..., description="Data de modificação do arquivo (UTC).")
    size_bytes: int = Field(..., description="Tamanho do arquivo em bytes.")
    id_column: str = Field(..., description="Coluna usada por /records/{id}.")
    tags: list[str] = Field(default_factory=list, description="Tags livres do sidecar.")
    readable: bool = Field(default=True, description="Se o arquivo pôde ser inspecionado.")
    error: str | None = Field(
        default=None, description="Motivo controlado quando ``readable`` é falso."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadados adicionais do sidecar."
    )


class DatasetListResponse(BaseModel):
    """Lista de datasets disponíveis."""

    items: list[DatasetMetadata]
    total: int = Field(..., description="Quantidade de datasets encontrados.")


class RecordPage(BaseModel):
    """Página de registros de um dataset."""

    dataset: str = Field(..., description="Dataset consultado.")
    items: list[dict[str, Any]] = Field(..., description="Registros da página atual.")
    total: int = Field(..., description="Total de registros após os filtros.")
    limit: int = Field(..., description="Limite aplicado nesta página.")
    offset: int = Field(..., description="Deslocamento aplicado nesta página.")
    fields: list[str] | None = Field(
        default=None, description="Projeção aplicada; ``null`` significa todas as colunas."
    )
    sort: str | None = Field(default=None, description="Coluna usada para ordenação.")
    order: Literal["asc", "desc"] | None = Field(default=None, description="Direção da ordenação.")


class RecordDetail(BaseModel):
    """Um registro identificado pela coluna de ID."""

    dataset: str
    id: str = Field(..., description="Valor do identificador consultado.")
    id_column: str = Field(..., description="Coluna usada como identificador.")
    record: dict[str, Any]


class AggregationItem(BaseModel):
    """Resultado de agregação para um grupo (ou para o dataset inteiro)."""

    group: dict[str, Any] = Field(
        default_factory=dict, description="Valores das colunas de group_by; vazio sem agrupamento."
    )
    values: dict[str, Any] = Field(
        ..., description="Métricas calculadas; ex.: ``{\"mean_score\": 0.42, \"count\": 10}``."
    )


class AggregationResponse(BaseModel):
    """Resposta de agregação genérica."""

    dataset: str
    aggregations: list[str] = Field(..., description="Agregações solicitadas.")
    columns: list[str] = Field(..., description="Colunas de entrada das agregações.")
    group_by: list[str] = Field(..., description="Colunas de agrupamento.")
    items: list[AggregationItem]
    total_groups: int = Field(..., description="Total de grupos antes da paginação.")
    limit: int = Field(..., description="Limite de grupos aplicado.")
    offset: int = Field(..., description="Deslocamento de grupos aplicado.")
