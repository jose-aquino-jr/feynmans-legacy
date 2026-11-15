"""Parsing e validação de parâmetros genéricos de consulta."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.services.errors import ApiError

ALLOWED_AGGREGATIONS = frozenset({"count", "mean", "min", "max", "sum"})


@dataclass(frozen=True)
class SortSpec:
    """Ordenação validada."""

    column: str
    order: Literal["asc", "desc"]


def parse_filters(
    query_items: Iterable[tuple[str, str]],
    reserved: frozenset[str],
) -> dict[str, list[str]]:
    """Converte a query string em filtros ``coluna -> [valores]``.

    Valores repetidos para a mesma coluna são combinados com OR; colunas
    diferentes são combinadas com AND. O prefixo ``filter_`` permite filtrar
    colunas cujo nome colida com parâmetros reservados.
    """
    filters: dict[str, list[str]] = {}
    for key, value in query_items:
        if key in reserved:
            continue
        column = key.removeprefix("filter_") if key.startswith("filter_") else key
        if not column:
            raise ApiError(
                400,
                "invalid_filter",
                "O nome do filtro não pode ser vazio.",
                {"filter": key},
            )
        filters.setdefault(column, []).append(value)
    return filters


def split_csv(raw: str | None, parameter: str) -> list[str] | None:
    """Divide um valor ``a,b,c`` em lista, preservando a ordem e removendo vazios."""
    if raw is None:
        return None
    values = [item.strip() for item in raw.split(",")]
    values = [item for item in values if item]
    if not values:
        raise ApiError(
            400,
            "invalid_parameter",
            f"O parâmetro '{parameter}' não pode ser vazio.",
            {"parameter": parameter},
        )
    return list(dict.fromkeys(values))


def flatten_multi(values: Sequence[str] | None, parameter: str) -> list[str]:
    """Aceita parâmetros repetidos e valores separados por vírgula."""
    if not values:
        return []
    flattened: list[str] = []
    for value in values:
        flattened.extend(part.strip() for part in value.split(",") if part.strip())
    if not flattened:
        raise ApiError(
            400,
            "invalid_parameter",
            f"O parâmetro '{parameter}' não pode ser vazio.",
            {"parameter": parameter},
        )
    return list(dict.fromkeys(flattened))


def validate_columns(
    requested: Iterable[str],
    available: Iterable[str],
    *,
    code: str,
    message: str,
    context: dict[str, object] | None = None,
) -> None:
    """Garante que todas as colunas solicitadas existem no dataset."""
    available_set = set(available)
    missing = [column for column in requested if column not in available_set]
    if missing:
        raise ApiError(
            400,
            code,
            message,
            {**(context or {}), "columns": missing},
        )


def parse_aggregations(values: Sequence[str] | None) -> list[str]:
    """Valida e normaliza a lista de agregações."""
    aggregations = flatten_multi(values, "agg") or ["count"]
    invalid = [item for item in aggregations if item not in ALLOWED_AGGREGATIONS]
    if invalid:
        raise ApiError(
            400,
            "invalid_aggregation",
            "Agregação não suportada.",
            {"invalid": invalid, "supported": sorted(ALLOWED_AGGREGATIONS)},
        )
    return aggregations


def parse_sort(
    sort: str | None,
    order: Literal["asc", "desc"],
    request_has_order: bool,
) -> SortSpec | None:
    """Valida a combinação ``sort``/``order``."""
    if sort is None:
        if request_has_order:
            raise ApiError(
                400,
                "invalid_parameter",
                "O parâmetro 'order' só pode ser usado junto com 'sort'.",
                {"parameter": "order"},
            )
        return None
    if order not in {"asc", "desc"}:
        raise ApiError(
            400,
            "invalid_parameter",
            "O parâmetro 'order' deve ser 'asc' ou 'desc'.",
            {"parameter": "order", "value": order},
        )
    if not sort.strip():
        raise ApiError(
            400,
            "invalid_parameter",
            "O parâmetro 'sort' não pode ser vazio.",
            {"parameter": "sort"},
        )
    return SortSpec(column=sort.strip(), order=order)
