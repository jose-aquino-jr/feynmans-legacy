"""Repositório de metadados dos artefatos de modelo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.schemas.model import ModelListResponse, ModelMetadata
from app.services.errors import ApiError
from app.services.files import (
    dict_value,
    optional_string,
    read_sidecar,
    scan_models,
    string_list,
)

logger = logging.getLogger("feynmans_legacy.api.models")

_KNOWN_SIDECAR_KEYS = frozenset(
    {
        "description",
        "tags",
        "algorithm",
        "framework",
        "target",
        "trained_at",
        "metrics",
        "params",
        "metadata",
    }
)


class ModelRepository:
    """Leitura de metadados, sem carregar/executar artefatos arbitrários."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _registry(self) -> dict[str, Path]:
        return scan_models(self.settings.models_dir)

    def _metadata_for(self, name: str, path: Path) -> ModelMetadata:
        stat = path.stat()
        sidecar = read_sidecar(path)
        suffix = path.suffix.lower().lstrip(".") or "unknown"
        sidecar_metadata = dict_value(sidecar.get("metadata"))
        for key, value in sidecar.items():
            if key not in _KNOWN_SIDECAR_KEYS and key not in sidecar_metadata:
                sidecar_metadata[key] = value

        description = optional_string(sidecar.get("description")) or (
            f"Artefato de modelo '{name}' ({suffix})."
        )
        return ModelMetadata(
            name=name,
            file=path.relative_to(self.settings.models_dir).as_posix(),
            format=suffix,
            description=description,
            size_bytes=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            tags=string_list(sidecar.get("tags")),
            algorithm=optional_string(sidecar.get("algorithm")),
            framework=optional_string(sidecar.get("framework")),
            target=optional_string(sidecar.get("target")),
            trained_at=optional_string(sidecar.get("trained_at")),
            metrics=dict_value(sidecar.get("metrics")),
            params=dict_value(sidecar.get("params")),
            metadata=sidecar_metadata,
        )

    def list_models(self) -> ModelListResponse:
        items: list[ModelMetadata] = []
        for name, path in self._registry().items():
            try:
                items.append(self._metadata_for(name, path))
            except OSError:
                logger.warning("model_disappeared", extra={"model": name})
        return ModelListResponse(items=items, total=len(items))

    def get_model(self, name: str) -> ModelMetadata:
        path = self._registry().get(name)
        if path is None:
            raise ApiError(
                404,
                "model_not_found",
                f"O modelo '{name}' não existe em models/.",
                {"model": name},
            )
        try:
            return self._metadata_for(name, path)
        except OSError as exc:
            raise ApiError(
                404,
                "model_not_found",
                f"O artefato do modelo '{name}' não está mais disponível.",
                {"model": name},
            ) from exc
