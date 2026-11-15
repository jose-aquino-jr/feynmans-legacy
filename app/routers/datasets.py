"""Router genérico de datasets, registros e agregações."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from app.config import Settings
from app.dependencies import (
    get_app_settings,
    get_current_principal,
    get_dataset_repository,
)
from app.schemas.common import error_responses
from app.schemas.dataset import (
    AggregationResponse,
    DatasetListResponse,
    DatasetMetadata,
    RecordDetail,
    RecordPage,
)
from app.services.datasets import DatasetRepository
from app.services.errors import ApiError
from app.services.parameters import (
    flatten_multi,
    parse_aggregations,
    parse_filters,
    parse_sort,
    split_csv,
)

RECORD_RESERVED = frozenset({"limit", "offset", "sort", "order", "fields"})
AGGREGATION_RESERVED = frozenset({"agg", "column", "group_by", "limit", "offset"})

DatasetPath = Annotated[
    str,
    Path(
        description="Nome lógico do dataset (caminho relativo sem extensão).",
        examples=["locais", "clusters/case1"],
    ),
]

LimitQuery = Annotated[
    int | None,
    Query(
        ge=1,
        description="Tamanho da página. Quando omitido, usa FL_DEFAULT_LIMIT.",
        examples=[50],
    ),
]
OffsetQuery = Annotated[
    int,
    Query(ge=0, description="Deslocamento inicial (base zero).", examples=[0]),
]
SortQuery = Annotated[
    str | None,
    Query(description="Coluna usada para ordenar.", examples=["score"]),
]
OrderQuery = Annotated[
    Literal["asc", "desc"],
    Query(description="Direção da ordenação.", examples=["desc"]),
]
FieldsQuery = Annotated[
    str | None,
    Query(
        description="Lista de colunas separadas por vírgula para projeção.",
        examples=["id,nome,score"],
    ),
]

router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
    dependencies=[Depends(get_current_principal)],
)


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="Lista datasets disponíveis",
    description=(
        "Varre `data/tratados/` e retorna metadados de cada CSV/Parquet: nome, "
        "descrição, colunas, número de registros, formato e data de atualização."
    ),
    responses=error_responses(500),
)
def list_datasets(
    repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
) -> DatasetListResponse:
    return repository.list_datasets()


@router.get(
    "/{dataset:path}/records",
    response_model=RecordPage,
    summary="Lista registros paginados",
    description=(
        "Aplica filtros dinâmicos (`?coluna=valor`), ordenação (`sort`/`order`), "
        "projeção (`fields`) e paginação (`limit`/`offset`). Filtros repetidos "
        "para a mesma coluna são combinados com OR; colunas diferentes com AND. "
        "Use `coluna=null` para filtrar valores ausentes."
    ),
    responses=error_responses(400, 404, 500),
)
def list_records(
    request: Request,
    dataset: DatasetPath,
    repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
    sort: SortQuery = None,
    order: OrderQuery = "asc",
    fields: FieldsQuery = None,
) -> RecordPage:
    effective_limit = _resolve_limit(limit, settings.default_limit, settings.max_limit)
    selected_fields = split_csv(fields, "fields")
    if selected_fields is not None and len(selected_fields) > settings.max_fields:
        raise ApiError(
            400,
            "invalid_parameter",
            f"O parâmetro 'fields' aceita no máximo {settings.max_fields} colunas.",
            {"parameter": "fields", "max_fields": settings.max_fields},
        )

    filters = parse_filters(request.query_params.multi_items(), RECORD_RESERVED)
    sort_spec = parse_sort(sort, order, "order" in request.query_params)
    return repository.get_records(
        dataset,
        filters=filters,
        sort=sort_spec,
        fields=selected_fields,
        limit=effective_limit,
        offset=offset,
    )


@router.get(
    "/{dataset:path}/records/{record_id}",
    response_model=RecordDetail,
    summary="Busca um registro pelo identificador",
    description=(
        "Localiza o registro cujo valor na coluna de ID (`id_column`) é igual a "
        "`record_id`. A coluna de ID pode ser declarada no sidecar do dataset."
    ),
    responses=error_responses(400, 404, 500),
)
def get_record(
    dataset: DatasetPath,
    record_id: Annotated[
        str,
        Path(description="Valor do identificador do registro.", examples=["1"]),
    ],
    repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
) -> RecordDetail:
    return repository.get_record(dataset, record_id)


@router.get(
    "/{dataset:path}/aggregations",
    response_model=AggregationResponse,
    summary="Agregações genéricas",
    description=(
        "Calcula `count`, `mean`, `min`, `max` e `sum`, opcionalmente agrupando "
        "por uma ou mais colunas. Aceita filtros dinâmicos como em /records. "
        "Os grupos também são paginados por `limit`/`offset`."
    ),
    responses=error_responses(400, 404, 500),
)
def aggregate_records(
    request: Request,
    dataset: DatasetPath,
    repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    agg: Annotated[
        list[str] | None,
        Query(
            description="Agregações (repetível ou separado por vírgula). Padrão: count.",
            examples=[["count"], ["mean", "max"]],
        ),
    ] = None,
    column: Annotated[
        list[str] | None,
        Query(
            description="Colunas de agregação (repetível ou separado por vírgula).",
            examples=[["score"]],
        ),
    ] = None,
    group_by: Annotated[
        list[str] | None,
        Query(
            description="Colunas de agrupamento (repetível ou separado por vírgula).",
            examples=[["clima"]],
        ),
    ] = None,
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            description="Máximo de grupos retornados. Padrão: FL_AGGREGATION_DEFAULT_LIMIT.",
            examples=[100],
        ),
    ] = None,
    offset: OffsetQuery = 0,
) -> AggregationResponse:
    effective_limit = _resolve_limit(
        limit,
        settings.aggregation_default_limit,
        settings.aggregation_max_limit,
        parameter="limit",
    )
    aggregations = parse_aggregations(agg)
    columns = flatten_multi(column, "column")
    groups = flatten_multi(group_by, "group_by")
    filters = parse_filters(request.query_params.multi_items(), AGGREGATION_RESERVED)
    return repository.get_aggregations(
        dataset,
        filters=filters,
        aggregations=aggregations,
        columns=columns,
        group_by=groups,
        limit=effective_limit,
        offset=offset,
    )


@router.get(
    "/{dataset:path}",
    response_model=DatasetMetadata,
    summary="Metadados de um dataset",
    description="Retorna o schema, a contagem de registros e os metadados de um dataset.",
    responses=error_responses(404, 500),
)
def get_dataset(
    dataset: DatasetPath,
    repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
) -> DatasetMetadata:
    return repository.get_dataset(dataset)


def _resolve_limit(
    requested: int | None,
    default: int,
    maximum: int,
    *,
    parameter: str = "limit",
) -> int:
    limit = default if requested is None else requested
    if limit > maximum:
        raise ApiError(
            400,
            "invalid_parameter",
            f"O parâmetro '{parameter}' deve ser menor ou igual a {maximum}.",
            {"parameter": parameter, "value": limit, "max": maximum},
        )
    return limit
