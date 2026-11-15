"""Leitura, inspeção e transformação de tabelas (CSV/Parquet)."""

from __future__ import annotations

import base64
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from app.services.errors import ApiError
from app.services.parameters import validate_columns

logger = logging.getLogger("feynmans_legacy.api.data")


@dataclass(frozen=True)
class TableInfo:
    """Schema e contagem de linhas obtidos sem materializar a tabela inteira."""

    columns: tuple[tuple[str, str], ...]
    row_count: int


def inspect_table(path: Path) -> TableInfo:
    """Inspeciona CSV/Parquet de forma leve.

    Para Parquet usa apenas o metadado. Para CSV usa leitura em streaming do
    PyArrow; se a inferência falhar, cai para o pandas (carregando o arquivo).
    """
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        parquet_file = pq.ParquetFile(path)
        columns = tuple(
            (field.name, str(field.type)) for field in parquet_file.schema_arrow
        )
        return TableInfo(columns=columns, row_count=parquet_file.metadata.num_rows)

    try:
        reader = pacsv.open_csv(path)
        columns = tuple((field.name, str(field.type)) for field in reader.schema)
        row_count = sum(batch.num_rows for batch in reader)
        return TableInfo(columns=columns, row_count=row_count)
    except Exception:
        frame = pd.read_csv(path, low_memory=False)
        columns = tuple((str(name), str(dtype)) for name, dtype in frame.dtypes.items())
        return TableInfo(columns=columns, row_count=len(frame))


def load_dataframe(path: Path) -> pd.DataFrame:
    """Carrega o arquivo inteiro em memória (o chamador deve cachear)."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, low_memory=False)
    elif suffix in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:  # pragma: no cover - o scanner só entrega formatos suportados
        raise ValueError(f"Formato não suportado: {suffix}")
    frame.columns = [str(column) for column in frame.columns]
    return frame


def apply_filters(
    frame: pd.DataFrame,
    filters: dict[str, list[str]],
    *,
    dataset: str,
) -> pd.DataFrame:
    """Aplica filtros de igualdade, com coerção pelo dtype da coluna."""
    filtered = frame
    for column, raw_values in filters.items():
        if column not in filtered.columns:
            raise ApiError(
                400,
                "invalid_filter_column",
                f"A coluna '{column}' não existe no dataset '{dataset}'.",
                {"dataset": dataset, "column": column},
            )

        series = filtered[column]
        mask = pd.Series(False, index=filtered.index)
        for raw_value in raw_values:
            if raw_value.strip().lower() == "null":
                mask = mask | series.isna()
                continue

            if pd.api.types.is_bool_dtype(series):
                parsed_bool = _parse_bool(raw_value, dataset, column)
                mask = mask | (series == parsed_bool)
            elif pd.api.types.is_numeric_dtype(series):
                try:
                    parsed_number = float(raw_value)
                except ValueError as exc:
                    raise ApiError(
                        400,
                        "invalid_filter_value",
                        f"O valor '{raw_value}' não é numérico para a coluna '{column}'.",
                        {"dataset": dataset, "column": column, "value": raw_value},
                    ) from exc
                mask = mask | (series == parsed_number)
            elif pd.api.types.is_datetime64_any_dtype(series):
                try:
                    parsed_date = pd.to_datetime(raw_value, errors="raise")
                    mask = mask | (series == parsed_date)
                except (ValueError, TypeError) as exc:
                    raise ApiError(
                        400,
                        "invalid_filter_value",
                        f"O valor '{raw_value}' não é uma data válida para a coluna '{column}'.",
                        {"dataset": dataset, "column": column, "value": raw_value},
                    ) from exc
            else:
                mask = mask | (series.astype("string") == raw_value)

        filtered = filtered.loc[mask]
    return filtered


def sort_frame(
    frame: pd.DataFrame,
    *,
    column: str | None,
    order: str,
    dataset: str,
) -> pd.DataFrame:
    """Ordena de forma estável; ``None`` em ``column`` mantém a ordem original."""
    if column is None:
        return frame
    if column not in frame.columns:
        raise ApiError(
            400,
            "invalid_sort_column",
            f"A coluna de ordenação '{column}' não existe no dataset '{dataset}'.",
            {"dataset": dataset, "column": column},
        )
    try:
        return frame.sort_values(
            by=column,
            ascending=order == "asc",
            kind="mergesort",
            na_position="last",
        )
    except TypeError as exc:
        raise ApiError(
            400,
            "invalid_sort",
            f"Não foi possível ordenar pela coluna '{column}'.",
            {"dataset": dataset, "column": column},
        ) from exc


def project_frame(
    frame: pd.DataFrame,
    fields: list[str] | None,
    *,
    dataset: str,
) -> pd.DataFrame:
    """Seleciona colunas na ordem solicitada."""
    if fields is None:
        return frame
    validate_columns(
        fields,
        frame.columns,
        code="invalid_field",
        message="Uma ou mais colunas solicitadas em 'fields' não existem no dataset.",
        context={"dataset": dataset, "parameter": "fields"},
    )
    return frame.loc[:, fields]


def frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte o DataFrame em JSON estritamente compatível."""
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        records.append({str(key): to_jsonable(value) for key, value in row.items()})
    return records


def to_jsonable(value: Any) -> Any:
    """Normaliza NaN/NaT, tipos numpy/pandas e datas para JSON."""
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.timedelta64):
        return str(pd.Timedelta(value))
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, (pd.Timedelta, timedelta)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _parse_bool(raw_value: str, dataset: str, column: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "sim", "yes"}:
        return True
    if normalized in {"false", "0", "nao", "não", "no"}:
        return False
    raise ApiError(
        400,
        "invalid_filter_value",
        f"O valor '{raw_value}' não é booleano para a coluna '{column}'.",
        {"dataset": dataset, "column": column, "value": raw_value},
    )


def detect_id_column(columns: list[str], declared: str | None = None) -> str:
    """Escolhe a coluna de ID: sidecar, nomes convencionais ou primeira coluna."""
    if declared and declared in columns:
        return declared
    by_lower = {column.lower(): column for column in columns}
    for candidate in ("id", "uuid", "record_id", "codigo", "code", "index"):
        if candidate in by_lower:
            return by_lower[candidate]
    if not columns:
        raise ApiError(
            500,
            "dataset_without_columns",
            "O dataset não possui colunas.",
            {},
        )
    return columns[0]


def aggregate_frame(
    frame: pd.DataFrame,
    *,
    dataset: str,
    aggregations: list[str],
    columns: list[str],
    group_by: list[str],
) -> list[dict[str, Any]]:
    """Calcula agregações por grupo, validando colunas e tipos."""
    validate_columns(
        columns,
        frame.columns,
        code="invalid_aggregation_column",
        message="Uma ou mais colunas de agregação não existem no dataset.",
        context={"dataset": dataset, "parameter": "column"},
    )
    validate_columns(
        group_by,
        frame.columns,
        code="invalid_group_by_column",
        message="Uma ou mais colunas de agrupamento não existem no dataset.",
        context={"dataset": dataset, "parameter": "group_by"},
    )
    if any(item in {"mean", "sum"} for item in aggregations) and not columns:
        raise ApiError(
            400,
            "invalid_aggregation_column",
            "As agregações 'mean' e 'sum' exigem ao menos uma coluna em 'column'.",
            {"dataset": dataset, "aggregations": aggregations},
        )
    needs_numeric = any(item in {"mean", "sum"} for item in aggregations)
    for column in columns:
        if needs_numeric and not pd.api.types.is_numeric_dtype(frame[column]):
            raise ApiError(
                400,
                "invalid_aggregation_column",
                f"A coluna '{column}' não é numérica para 'mean'/'sum'.",
                {"dataset": dataset, "column": column},
            )

    def compute(group: pd.DataFrame) -> dict[str, Any]:
        values: dict[str, Any] = {}
        if "count" in aggregations:
            if columns:
                for column in columns:
                    values[f"count_{column}"] = int(group[column].count())
            else:
                values["count"] = int(len(group))
        for aggregation in aggregations:
            if aggregation == "count":
                continue
            for column in columns:
                series = group[column]
                if aggregation == "mean":
                    result = series.mean()
                elif aggregation == "sum":
                    result = series.sum(min_count=1)
                elif aggregation == "min":
                    result = series.min()
                elif aggregation == "max":
                    result = series.max()
                else:  # pragma: no cover - validado antes
                    result = None
                values[f"{aggregation}_{column}"] = to_jsonable(result)
        return values

    items: list[dict[str, Any]] = []
    if group_by:
        grouped = frame.groupby(group_by, dropna=False, observed=True, sort=True)
        for keys, group in grouped:
            key_values = keys if isinstance(keys, tuple) else (keys,)
            group_values = {
                column: to_jsonable(value)
                for column, value in zip(group_by, key_values, strict=True)
            }
            items.append({"group": group_values, "values": compute(group)})
    else:
        items.append({"group": {}, "values": compute(frame)})
    return items
