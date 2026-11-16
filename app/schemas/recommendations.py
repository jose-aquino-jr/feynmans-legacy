"""Contrato das recomendações temporais (top K por base para um AAAAMM)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Corpo = Literal["lua", "marte"]
Estrategia = Literal["recursiva", "auto", "sazonal"]
Origem = Literal["observada", "prevista", "extrapolada", "cenario_sazonal"]
StatusGrupo = Literal["ok", "parcial", "sem_dados", "sem_candidatos", "nicho_incompativel"]


class BaseOpcao(BaseModel):
    base_id: str = Field(..., examples=["MARTE_JEZERO"])
    corpo: Corpo
    nome: str
    latitude: float | None = None
    longitude: float | None = None
    raio_km: float | None = None
    nichos: list[str] = Field(..., description="Nichos aceitos pela base (inclui Todos).")


class Publicacao(BaseModel):
    """Identidade dos artefatos que geram a nota."""

    corte: int = Field(..., description="Último AAAAMM observado (origem do pacote).")
    horizontes_diretos: dict[str, list[int]]
    estrategias: list[Estrategia]
    estrategia_padrao_futuro: Estrategia = "recursiva"
    algoritmo: str
    modelo_sha256: str
    historico_sha256: str
    trajetoria: str = Field(..., description="Chave da projeção recursiva em cache.")


class OpcoesResponse(BaseModel):
    bases: list[BaseOpcao]
    meses_observados: list[int]
    anomes_max: int
    k_max: int
    cobertura_minima_padrao: float = 0.7
    publicacao: Publicacao


class Criterio(BaseModel):
    variavel: str
    nome: str
    unidade: str
    alvo: float
    tolerancia: float
    peso: float
    tipo_alvo: str | None = None
    fonte: str | None = None


class Candidato(BaseModel):
    posicao: int = Field(..., description="Posição no ranking completo da base (1 = melhor).")
    location_id: str
    latitude: float
    longitude: float
    nota: float
    cobertura: float
    cluster: int | None = None
    valores: dict[str, float | None] = Field(..., description="Valor terrestre por variável.")
    notas_criterios: dict[str, float | None] = Field(
        ..., description="Nota 0–100 de cada critério (nula sem dado).")
    criterios_sem_dado: list[str] = Field(default_factory=list)


class GrupoBase(BaseModel):
    base_id: str
    corpo: Corpo
    nome: str
    latitude: float | None = None
    longitude: float | None = None
    status: StatusGrupo = Field(
        ...,
        description=(
            "ok; parcial (algum critério sem dado em todo o recorte, mas há candidatos); "
            "sem_dados (os critérios ausentes impedem atingir a cobertura); "
            "sem_candidatos (há dados, nenhum local atinge a cobertura); "
            "nicho_incompativel (a base não tem esse nicho)."
        ),
    )
    criterios: list[Criterio]
    criterios_ausentes: list[str] = Field(
        default_factory=list, description="Critérios sem nenhum valor terrestre no recorte.")
    total_elegiveis: int
    candidatos: list[Candidato]


class RecomendacoesResponse(BaseModel):
    anomes: int
    nicho: str
    origem: Origem
    estrategia: Estrategia = Field(..., description="Estratégia efetivamente usada.")
    horizonte_meses: int = Field(..., description="Meses após o corte (0 se observado).")
    mes_base_cenario: int | None = Field(
        None, description="Mês observado usado no cenário sazonal.")
    anomes_cluster: int | None = None
    rotulo: str | None = Field(None, examples=["Projeção exploratória"])
    metodos: dict[str, str] = Field(
        default_factory=dict, description="Método por variável no mês (ex.: lightgbm_h3).")
    cobertura_minima: float
    k: int
    offset: int
    publicacao: Publicacao
    resultados: list[GrupoBase]


class Calculando(BaseModel):
    status: Literal["calculando"] = "calculando"
    anomes: int
    estrategia: Estrategia
    repetir_em_segundos: int
    tarefa_id: str
    meses_calculados: int = Field(..., description="Meses já projetados nesta trajetória.")
    meses_necessarios: int = Field(..., description="Meses do corte até o destino.")
    na_fila: bool = Field(..., description="Ainda aguardando um worker livre.")
