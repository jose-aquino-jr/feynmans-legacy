"""Schemas Pydantic v2 usados no contrato da API."""

from __future__ import annotations

from app.schemas.common import ErrorDetail, ErrorResponse, error_responses
from app.schemas.dataset import (
    AggregationItem,
    AggregationResponse,
    ColumnMetadata,
    DatasetListResponse,
    DatasetMetadata,
    RecordDetail,
    RecordPage,
)
from app.schemas.health import HealthResponse
from app.schemas.model import ModelListResponse, ModelMetadata

__all__ = [
    "AggregationItem",
    "AggregationResponse",
    "ColumnMetadata",
    "DatasetListResponse",
    "DatasetMetadata",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "ModelListResponse",
    "ModelMetadata",
    "RecordDetail",
    "RecordPage",
    "error_responses",
]
