"""Schema único de erro e utilitários de documentação."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

ErrorResponses = dict[int | str, dict[str, Any]]


class ErrorDetail(BaseModel):
    """Detalhe padronizado de um erro da API."""

    code: str = Field(
        ...,
        description="Código estável do erro, adequado para tratamento pelo cliente.",
        examples=["invalid_filter_column"],
    )
    message: str = Field(
        ...,
        description="Mensagem legível para humanos.",
        examples=["A coluna 'foo' não existe no dataset 'locais'."],
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Informações adicionais específicas do erro.",
        examples=[{"column": "foo", "dataset": "locais"}],
    )


class ErrorResponse(BaseModel):
    """Formato único de erro: ``{\"detail\": {\"code\", \"message\", \"context\"}}``."""

    detail: ErrorDetail


def error_responses(*status_codes: int) -> ErrorResponses:
    """Monta o mapa de respostas de erro para o OpenAPI."""
    descriptions = {
        400: "Parâmetro de requisição inválido.",
        404: "Recurso não encontrado.",
        409: "Conflito ao resolver o recurso.",
        422: "Parâmetro de requisição inválido.",
        500: "Erro interno controlado (sem stack trace no corpo).",
    }
    return {
        code: {"model": ErrorResponse, "description": descriptions.get(code, "Erro.")}
        for code in status_codes
    }
