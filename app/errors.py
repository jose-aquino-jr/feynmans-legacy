"""Handlers globais que garantem o formato único de erro."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorResponse
from app.services.errors import ApiError

logger = logging.getLogger("feynmans_legacy.api.errors")


def _error_response(
    status_code: int,
    code: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        detail=ErrorDetail(code=code, message=message, context=context or {})
    ).model_dump(mode="json")
    return JSONResponse(status_code=status_code, content=payload)


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _safe_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ())]
        errors.append(
            {
                "loc": location,
                "msg": str(error.get("msg", "valor inválido")),
                "type": str(error.get("type", "value_error")),
            }
        )
    return errors


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers no app FastAPI."""

    @app.exception_handler(ApiError)
    async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "api_error",
                extra={"request_id": _request_id(request), "status_code": exc.status_code},
            )
        return _error_response(exc.status_code, exc.code, exc.message, exc.context)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            400,
            "invalid_parameter",
            "Parâmetros de requisição inválidos.",
            {"errors": _safe_validation_errors(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        codes = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
        }
        code = codes.get(exc.status_code, "http_error")
        messages = {
            401: "Autenticação necessária.",
            403: "Acesso negado.",
            404: "Recurso não encontrado.",
            405: "Método HTTP não permitido.",
        }
        message = messages.get(exc.status_code, str(exc.detail) or "Erro HTTP.")
        context: dict[str, Any] = {
            "path": request.url.path,
            "method": request.method,
        }
        return _error_response(exc.status_code, code, message, context)

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={"request_id": _request_id(request), "status_code": 500},
        )
        return _error_response(
            500,
            "internal_error",
            "Erro interno inesperado. Consulte os logs do servidor.",
            {"request_id": _request_id(request)},
        )
