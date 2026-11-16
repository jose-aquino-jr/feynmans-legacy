"""Aplicação FastAPI do Feynman's Legacy.

Execução local:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import Settings, get_settings
from app.errors import register_exception_handlers
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.routers import analogos, datasets, health, models, recommendations
from app.schemas.common import ErrorResponse
from app.services.analogos import AnalogRepository
from app.services.datasets import DatasetRepository
from app.services.models import ModelRepository
from app.services.recommendations import RecommendationService

API_DESCRIPTION = """
API **somente leitura** para consumo dos dados processados e artefatos de modelo
do projeto *Feynman's Legacy*.

## Fontes de dados

- `data/tratados/`: datasets em CSV/Parquet.
- `models/`: artefatos de modelos (metadados apenas; nada é executado).

## Contrato

- Paginação: `limit`/`offset`, com `items`, `total`, `limit`, `offset`.
- Filtros dinâmicos: `?coluna=valor` (repetir a coluna combina com OR).
- Ordenação: `sort=campo&order=asc|desc`.
- Projeção: `fields=a,b,c`.
- Erros: `{"detail": {"code": "...", "message": "...", "context": {...}}}`.

A API não escreve, altera ou remove dados. Autenticação pode ser adicionada pelo
ponto de extensão `app.dependencies.get_current_principal`.
"""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Disponibilidade da API e dos diretórios de dados.",
    },
    {
        "name": "datasets",
        "description": (
            "Descoberta de datasets, consulta paginada de registros, busca por ID "
            "e agregações genéricas."
        ),
    },
    {
        "name": "models",
        "description": "Metadados dos artefatos presentes em `models/`.",
    },
    {
        "name": "recomendacoes",
        "description": (
            "Top K locais terrestres por base para um ano/mês: observado, projeção "
            "LightGBM recursiva (202 enquanto calcula) ou cenário sazonal."
        ),
    },
    {
        "name": "analogos",
        "description": (
            "Relações entre bases da Lua e de Marte e locais terrestres, com notas por "
            "nicho, para o mapa 3D. Geradas por `scripts/gerar_analogos.py`."
        ),
    },
]

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head", "trace"})


def _custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Gera o OpenAPI removendo o 422 padrão (a API devolve 400 padronizado)."""
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault(
        "ErrorResponse",
        ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}"),
    )

    error_response = {
        "description": "Parâmetro de requisição inválido.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
            }
        },
    }
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            if "422" in responses:
                responses["400"] = error_response
                responses.pop("422")

    app.openapi_schema = schema
    return schema


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação; a injeção de ``Settings`` facilita os testes."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        summary="API de leitura dos datasets e modelos do Feynman's Legacy.",
        description=API_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": "Feynman's Legacy",
            "url": "https://github.com/jose-aquino-jr/feynmans-legacy",
        },
        license_info={"name": "A definir"},
    )

    app.state.settings = active_settings
    app.state.started_at = time.perf_counter()
    app.state.dataset_repository = DatasetRepository(active_settings)
    app.state.model_repository = ModelRepository(active_settings)
    app.state.analog_repository = AnalogRepository(active_settings)
    app.state.recommendation_service = RecommendationService(active_settings)

    # O middleware adicionado por último fica mais externo: CORS por fora.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=active_settings.cors_allow_credentials,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
        max_age=600,
    )

    app.include_router(health.router)
    app.include_router(datasets.router, prefix=active_settings.api_v1_prefix)
    app.include_router(models.router, prefix=active_settings.api_v1_prefix)
    app.include_router(recommendations.router, prefix=active_settings.api_v1_prefix)
    app.include_router(analogos.router, prefix=active_settings.api_v1_prefix)

    register_exception_handlers(app)

    def _openapi() -> dict[str, Any]:
        return _custom_openapi(app)

    app.openapi = _openapi  # type: ignore[method-assign]

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """Atalhos para descoberta da API (sem HTML próprio)."""
        return {
            "name": active_settings.app_name,
            "version": active_settings.app_version,
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health",
            "datasets": f"{active_settings.api_v1_prefix}/datasets",
            "models": f"{active_settings.api_v1_prefix}/models",
            "analogos": f"{active_settings.api_v1_prefix}/analogos/bases",
        }

    return app


app = create_app()
