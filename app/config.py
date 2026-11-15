"""Configuração central da API, carregada de variáveis de ambiente ``FL_*``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuração da aplicação.

    Todas as variáveis podem ser definidas no ambiente ou em um arquivo ``.env``
    na raiz do projeto. O prefixo obrigatório é ``FL_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="FL_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Feynman's Legacy API"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"

    # Diretórios de dados. Valores relativos são resolvidos a partir da raiz do projeto.
    data_dir: Path = PROJECT_ROOT / "data" / "tratados"
    models_dir: Path = PROJECT_ROOT / "models"

    default_limit: int = Field(default=100, ge=1)
    max_limit: int = Field(default=1_000, ge=1)
    max_fields: int = Field(default=100, ge=1)
    aggregation_default_limit: int = Field(default=1_000, ge=1)
    aggregation_max_limit: int = Field(default=10_000, ge=1)

    # CORS: nunca use "*" em produção.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:4200", "http://localhost:3000", "http://localhost:5173"
        ]
    )
    cors_allow_credentials: bool = False

    log_level: str = "INFO"
    cache_max_entries: int = Field(default=32, ge=1)

    @field_validator("data_dir", "models_dir", mode="before")
    @classmethod
    def _resolve_path(cls, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Aceita JSON (``["a", "b"]``) ou lista separada por vírgulas."""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("FL_CORS_ORIGINS deve ser uma lista JSON.")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("FL_CORS_ORIGINS inválido.")

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("FL_LOG_LEVEL deve ser CRITICAL, ERROR, WARNING, INFO ou DEBUG.")
        return level

    @model_validator(mode="after")
    def _validate_limits(self) -> Settings:
        if self.default_limit > self.max_limit:
            raise ValueError("FL_DEFAULT_LIMIT não pode ser maior que FL_MAX_LIMIT.")
        if self.aggregation_default_limit > self.aggregation_max_limit:
            raise ValueError(
                "FL_AGGREGATION_DEFAULT_LIMIT não pode ser maior que FL_AGGREGATION_MAX_LIMIT."
            )
        if self.environment == "production" and "*" in self.cors_origins:
            raise ValueError("FL_CORS_ORIGINS não pode conter '*' em produção.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a configuração padrão (cacheada para uso pela CLI/uvicorn)."""
    return Settings()
