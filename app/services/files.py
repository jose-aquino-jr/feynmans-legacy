"""Descoberta de arquivos e leitura de sidecars de metadados."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("feynmans_legacy.api.files")

type DatasetFormat = Literal["csv", "parquet"]

DATASET_FORMATS: dict[str, DatasetFormat] = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
}
DATASET_PRIORITY: dict[str, int] = {".parquet": 0, ".pq": 1, ".csv": 2}

MODEL_SUFFIXES: frozenset[str] = frozenset(
    {
        ".joblib",
        ".pkl",
        ".pickle",
        ".onnx",
        ".h5",
        ".hdf5",
        ".pt",
        ".pth",
        ".keras",
        ".json",
        ".ubj",
        ".cbm",
        ".lgb",
        ".xgb",
        ".bin",
        ".model",
        ".txt",
    }
)


def _is_hidden(relative: Path) -> bool:
    return any(part.startswith(".") for part in relative.parts)


def _relative_name(relative: Path) -> str:
    return relative.with_suffix("").as_posix()


def scan_datasets(root: Path) -> dict[str, Path]:
    """Mapeia ``nome lógico -> arquivo`` para CSV/Parquet em ``data/tratados``.

    Se houver o mesmo nome em formatos diferentes, Parquet tem prioridade.
    """
    if not root.is_dir():
        return {}

    candidates: list[tuple[str, Path, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_hidden(relative):
            continue
        suffix = path.suffix.lower()
        if suffix not in DATASET_FORMATS:
            continue
        candidates.append((_relative_name(relative), path, suffix))

    registry: dict[str, Path] = {}
    suffixes: dict[str, str] = {}
    for name, path, suffix in sorted(candidates, key=lambda item: item[1].as_posix()):
        previous = registry.get(name)
        if previous is None or DATASET_PRIORITY[suffix] < DATASET_PRIORITY[suffixes[name]]:
            if previous is not None:
                logger.warning(
                    "duplicate_dataset_name",
                    extra={
                        "dataset": name,
                        "kept": path.as_posix(),
                        "ignored": previous.as_posix(),
                    },
                )
            registry[name] = path
            suffixes[name] = suffix
        else:
            logger.warning(
                "duplicate_dataset_name",
                extra={"dataset": name, "kept": previous.as_posix(), "ignored": path.as_posix()},
            )
    return dict(sorted(registry.items()))


def scan_models(root: Path) -> dict[str, Path]:
    """Mapeia ``nome lógico -> artefato`` para arquivos conhecidos em ``models/``."""
    if not root.is_dir():
        return {}

    registry: dict[str, Path] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_hidden(relative):
            continue
        if path.name.endswith(".meta.json"):
            continue
        if path.suffix.lower() not in MODEL_SUFFIXES:
            continue
        name = _relative_name(relative)
        if name in registry:
            logger.warning(
                "duplicate_model_name",
                extra={
                    "model": name,
                    "kept": registry[name].as_posix(),
                    "ignored": path.as_posix(),
                },
            )
            continue
        registry[name] = path
    return dict(sorted(registry.items()))


def read_sidecar(path: Path) -> dict[str, Any]:
    """Lê e mescla sidecars ``<nome>.meta.json`` e ``<arquivo>.meta.json``."""
    candidates = (
        path.with_suffix(".meta.json"),
        path.with_name(f"{path.name}.meta.json"),
    )
    merged: dict[str, Any] = {}
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("invalid_sidecar", extra={"file": candidate.as_posix()})
            continue
        if isinstance(data, dict):
            merged.update(data)
    return merged


def string_list(value: Any) -> list[str]:
    """Normaliza tags para ``list[str]``."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def dict_value(value: Any) -> dict[str, Any]:
    """Retorna o dicionário ou um dicionário vazio."""
    return dict(value) if isinstance(value, dict) else {}


def optional_string(value: Any) -> str | None:
    return str(value) if isinstance(value, (str, int, float)) and str(value).strip() else None
