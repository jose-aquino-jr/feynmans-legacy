"""Contrato dos análogos Terra ↔ Lua/Marte consumidos pelo mapa 3D."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Corpo = Literal["lua", "marte"]
TipoPar = Literal["destaque", "geral", "especialista"]


class Ponto(BaseModel):
    """Posição de um marcador no globo."""

    latitude: float = Field(..., description="Latitude em graus.", examples=[18.38])
    longitude: float = Field(
        ..., description="Longitude leste em graus, em [-180, 180].", examples=[77.58]
    )
    raio_km: float = Field(..., description="Raio sugerido do destaque no globo.")


class BaseEspacial(Ponto):
    """Base de referência na Lua ou em Marte."""

    base_id: str = Field(..., examples=["MARTE_JEZERO"])
    corpo: Corpo
    nome: str = Field(..., examples=["Cratera Jezero"])
    descricao: str
    n_pares: int = Field(..., description="Quantidade de locais terrestres relacionados.")
    melhor_location_id: str | None = None
    melhor_nota: float | None = Field(default=None, description="Maior nota geral (0–100).")


class LocalTerra(Ponto):
    """Local terrestre relacionado a pelo menos uma base."""

    location_id: str = Field(..., examples=["T042068"])
    nome: str = Field(..., examples=["Deserto da Núbia — Sudão"])
    regiao: str | None = None
    pais: str | None = None
    descricao: str | None = Field(default=None, description="Texto curado dos destaques.")
    destaque: bool = Field(..., description="Local padrão do software.")
    n_pares: int
    melhor_nota: float | None = None
    temperatura_media_c: float | None = None
    precipitacao_mm_dia: float | None = None
    elevacao_media_m: float | None = None
    ndvi: float | None = None


class Par(BaseModel):
    """Relação entre uma base espacial e um local terrestre."""

    par_id: str = Field(..., examples=["MARTE_JEZERO__T042068"])
    corpo: Corpo
    base_id: str
    location_id: str
    tipo: TipoPar = Field(
        ...,
        description=(
            "destaque: local padrão; geral: entre as melhores notas gerais; "
            "especialista: muito parecido em um nicho."
        ),
    )
    destaque: bool
    rank_base: int = Field(..., description="Posição entre os pares da mesma base (1 = melhor).")
    nota_geral: float | None = Field(
        default=None, description="Nota 0–100 no perfil completo; nula com pouca cobertura."
    )
    cobertura: float = Field(..., description="Fração do peso do perfil com dados.")
    nichos_destaque: list[str] = Field(
        default_factory=list, description="Nichos que motivaram a escolha."
    )
    pontos_fortes: list[str] = Field(default_factory=list, description="Nichos com nota >= 75.")
    pontos_fracos: list[str] = Field(default_factory=list, description="Nichos com nota < 50.")
    nichos: dict[str, float | None] = Field(
        default_factory=dict, description="Nota 0–100 por nicho."
    )


class ParComLocal(Par):
    local: LocalTerra


class ParComBase(Par):
    base: BaseEspacial


class BaseListResponse(BaseModel):
    items: list[BaseEspacial]
    total: int


class BaseDetalhe(BaseModel):
    """Uma base e os locais terrestres relacionados, prontos para desenhar no 3D."""

    base: BaseEspacial
    pares: list[ParComLocal]
    total: int = Field(..., description="Pares após os filtros, antes do limite.")


class LocalListResponse(BaseModel):
    items: list[LocalTerra]
    total: int
    limit: int
    offset: int


class LocalDetalhe(BaseModel):
    """Um local terrestre e todas as bases relacionadas."""

    local: LocalTerra
    pares: list[ParComBase]


class Nicho(BaseModel):
    """Dimensão de comparação usada nas notas por nicho."""

    nicho: str = Field(..., examples=["geologia"])
    nome: str = Field(..., examples=["Geologia"])
    corpos: list[Corpo]


class NichoListResponse(BaseModel):
    items: list[Nicho]
    total: int


class PontoSerie(BaseModel):
    anomes: int = Field(..., examples=[202609])
    origem: Literal["observada", "prevista"]
    nota: float | None
    cobertura: float | None


class ParDetalhe(BaseModel):
    """Par completo: base, local, notas por nicho e série mensal da nota geral."""

    par: Par
    base: BaseEspacial
    local: LocalTerra
    serie: list[PontoSerie]
