"""Repositório de datasets: metadados, registros e agregações."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings
from app.schemas.dataset import (
    AggregationItem,
    AggregationResponse,
    ColumnMetadata,
    DatasetListResponse,
    DatasetMetadata,
    RecordDetail,
    RecordPage,
)
from app.services.cache import BoundedCache
from app.services.dataframe import (
    TableInfo,
    aggregate_frame,
    apply_filters,
    detect_id_column,
    frame_to_records,
    inspect_table,
    load_dataframe,
    project_frame,
    sort_frame,
)
from app.services.errors import ApiError
from app.services.files import (
    DATASET_FORMATS,
    dict_value,
    optional_string,
    read_sidecar,
    scan_datasets,
    string_list,
)
from app.services.parameters import SortSpec

logger = logging.getLogger("feynmans_legacy.api.datasets")


class DatasetRepository:
    """Camada de leitura isolada das rotas."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._frame_cache: BoundedCache[tuple[str, int, int], pd.DataFrame] = BoundedCache(
            settings.cache_max_entries
        )
        self._info_cache: BoundedCache[tuple[str, int, int], TableInfo] = BoundedCache(
            settings.cache_max_entries
        )

    # ------------------------------------------------------------------ registry
    def _registry(self) -> dict[str, Path]:
        return scan_datasets(self.settings.data_dir)

    def _path_for(self, dataset: str) -> Path:
        path = self._registry().get(dataset)
        if path is None:
            raise ApiError(
                404,
                "dataset_not_found",
                f"O dataset '{dataset}' não existe em data/tratados.",
                {"dataset": dataset},
            )
        return path

    @staticmethod
    def _cache_key(path: Path) -> tuple[str, int, int]:
        try:
            stat = path.stat()
        except OSError as exc:
            raise ApiError(
                404,
                "dataset_not_found",
                "O arquivo do dataset não está mais disponível.",
                {"dataset": path.name},
            ) from exc
        return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)

    # ------------------------------------------------------------------- loading
    def _table_info(self, path: Path) -> TableInfo:
        key = self._cache_key(path)
        return self._info_cache.get_or_load(key, lambda: inspect_table(path))

    def _frame(self, dataset: str, path: Path) -> pd.DataFrame:
        key = self._cache_key(path)
        try:
            return self._frame_cache.get_or_load(key, lambda: load_dataframe(path))
        except ApiError:
            raise
        except Exception as exc:
            logger.exception(
                "dataset_load_failed",
                extra={"dataset": dataset, "file": path.as_posix()},
            )
            raise ApiError(
                500,
                "dataset_read_error",
                f"Não foi possível ler o dataset '{dataset}'.",
                {"dataset": dataset},
            ) from exc

    # ------------------------------------------------------------------ metadata
    def _metadata_for(self, name: str, path: Path) -> DatasetMetadata:
        stat = path.stat()
        sidecar = read_sidecar(path)
        suffix = path.suffix.lower()
        file_format = DATASET_FORMATS[suffix]

        columns: list[ColumnMetadata] = []
        row_count: int | None = None
        readable = True
        error: str | None = None
        try:
            info = self._table_info(path)
            row_count = info.row_count
            descriptions = _column_descriptions(sidecar)
            columns = [
                ColumnMetadata(
                    name=column,
                    dtype=dtype,
                    description=descriptions.get(column),
                )
                for column, dtype in info.columns
            ]
        except Exception:
            readable = False
            error = "Arquivo ilegível. Consulte os logs do servidor."
            logger.exception(
                "dataset_metadata_failed",
                extra={"dataset": name, "file": path.as_posix()},
            )

        column_names = [column.name for column in columns]
        declared_id = optional_string(sidecar.get("id_column"))
        try:
            id_column = detect_id_column(column_names, declared_id)
        except ApiError:
            id_column = declared_id or "id"

        description = optional_string(sidecar.get("description")) or (
            f"Dataset '{name}' em formato {file_format}."
        )
        metadata = dict_value(sidecar.get("metadata"))
        for key in ("source", "license", "notes", "owner", "version"):
            if key in sidecar and key not in metadata:
                metadata[key] = sidecar[key]

        return DatasetMetadata(
            name=name,
            file=path.relative_to(self.settings.data_dir).as_posix(),
            format=file_format,
            description=description,
            columns=columns,
            row_count=row_count,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            size_bytes=stat.st_size,
            id_column=id_column,
            tags=string_list(sidecar.get("tags")),
            readable=readable,
            error=error,
            metadata=metadata,
        )

    def list_datasets(self) -> DatasetListResponse:
        items: list[DatasetMetadata] = []
        for name, path in self._registry().items():
            try:
                items.append(self._metadata_for(name, path))
            except OSError:
                logger.warning("dataset_disappeared", extra={"dataset": name})
        return DatasetListResponse(items=items, total=len(items))

    def get_dataset(self, dataset: str) -> DatasetMetadata:
        path = self._path_for(dataset)
        try:
            return self._metadata_for(dataset, path)
        except OSError as exc:
            raise ApiError(
                404,
                "dataset_not_found",
                f"O arquivo do dataset '{dataset}' não está mais disponível.",
                {"dataset": dataset},
            ) from exc

    # ------------------------------------------------------------------- records
    def get_records(
        self,
        dataset: str,
        *,
        filters: dict[str, list[str]],
        sort: SortSpec | None,
        fields: list[str] | None,
        limit: int,
        offset: int,
    ) -> RecordPage:
        frame = self._frame(dataset, self._path_for(dataset))
        frame = apply_filters(frame, filters, dataset=dataset)
        frame = sort_frame(
            frame,
            column=sort.column if sort else None,
            order=sort.order if sort else "asc",
            dataset=dataset,
        )
        total = int(len(frame))
        page = frame.iloc[offset : offset + limit]
        page = project_frame(page, fields, dataset=dataset)
        return RecordPage(
            dataset=dataset,
            items=frame_to_records(page),
            total=total,
            limit=limit,
            offset=offset,
            fields=fields,
            sort=sort.column if sort else None,
            order=sort.order if sort else None,
        )

    def get_record(self, dataset: str, record_id: str) -> RecordDetail:
        path = self._path_for(dataset)
        frame = self._frame(dataset, path)
        sidecar = read_sidecar(path)
        id_column = detect_id_column(
            [str(column) for column in frame.columns],
            optional_string(sidecar.get("id_column")),
        )
        series = frame[id_column]
        mask = series.astype("string") == record_id
        if pd.api.types.is_numeric_dtype(series):
            try:
                mask = mask | (series == float(record_id))
            except ValueError:
                pass
        matches = frame.loc[mask]
        if matches.empty:
            raise ApiError(
                404,
                "record_not_found",
                f"Registro '{record_id}' não encontrado no dataset '{dataset}'.",
                {"dataset": dataset, "id": record_id, "id_column": id_column},
            )
        record = frame_to_records(matches.iloc[[0]])[0]
        return RecordDetail(
            dataset=dataset,
            id=record_id,
            id_column=id_column,
            record=record,
        )

    # --------------------------------------------------------------- aggregation
    def get_aggregations(
        self,
        dataset: str,
        *,
        filters: dict[str, list[str]],
        aggregations: list[str],
        columns: list[str],
        group_by: list[str],
        limit: int,
        offset: int,
    ) -> AggregationResponse:
        frame = self._frame(dataset, self._path_for(dataset))
        frame = apply_filters(frame, filters, dataset=dataset)
        raw_items = aggregate_frame(
            frame,
            dataset=dataset,
            aggregations=aggregations,
            columns=columns,
            group_by=group_by,
        )
        total_groups = len(raw_items)
        page = raw_items[offset : offset + limit]
        items = [
            AggregationItem(group=item["group"], values=item["values"]) for item in page
        ]
        return AggregationResponse(
            dataset=dataset,
            aggregations=aggregations,
            columns=columns,
            group_by=group_by,
            items=items,
            total_groups=total_groups,
            limit=limit,
            offset=offset,
        )


def _column_descriptions(sidecar: dict[str, Any]) -> dict[str, str]:
    """Extrai descrições de colunas de sidecars em formatos comuns."""
    raw = sidecar.get("column_descriptions", sidecar.get("columns"))
    if isinstance(raw, dict):
        descriptions: dict[str, str] = {}
        for key, value in raw.items():
            if isinstance(value, str):
                descriptions[str(key)] = value
            elif isinstance(value, dict) and isinstance(value.get("description"), str):
                descriptions[str(key)] = value["description"]
        return descriptions
    if isinstance(raw, list):
        descriptions = {}
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                description = item.get("description")
                if isinstance(description, str):
                    descriptions[item["name"]] = description
        return descriptions
    return {}
