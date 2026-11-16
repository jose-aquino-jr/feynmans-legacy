"""Contrato dos análogos Terra ↔ Lua/Marte consumidos pelo mapa 3D."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Corpo = Literal["lua", "marte"]
TipoPar = Literal["destaque", "geral", "especialista", "custo_beneficio"]


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
    melhor_custo_beneficio_location_id: str | None = None
    melhor_custo_beneficio: float | None = Field(
        default=None, description="Maior custo-benefício entre os pares (0–100).")
    explicacao: str | None = Field(
        default=None, description="Resumo: melhores análogos e o que a Terra reproduz bem ou mal.")


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
    melhor_custo_beneficio: float | None = None
    nota_logistica: float | None = Field(
        default=None, description="0–100: proximidade dos EUA, da base de apoio e redundância.")
    distancia_eua_km: float | None = Field(
        default=None, description="Distância à instalação dos EUA mais próxima.")
    apoio_principal_id: str | None = None
    apoio_principal_nome: str | None = None
    distancia_apoio_km: float | None = None
    n_apoios_raio: int | None = Field(
        default=None, description="Bases de apoio no raio de rotas (alternativas).")
    nota_eua: float | None = None
    nota_apoio: float | None = None
    nota_rotas: float | None = None
    temperatura_media_c: float | None = None
    precipitacao_mm_dia: float | None = None
    elevacao_media_m: float | None = None
    ndvi: float | None = None
    explicacao: str | None = Field(
        default=None, description="Resumo: bases relacionadas, melhores usos, logística e clima.")
    usos_recomendados: list[str] = Field(
        default_factory=list, description="Até 2 utilidades com nota >= 70 (ids de /filtros).")


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
    nota_logistica: float | None = None
    custo_beneficio: float | None = Field(
        default=None, description="raiz(nota_geral × nota_logistica), 0–100.")
    rank_custo_beneficio: int | None = Field(
        default=None, description="Posição pelo custo-benefício entre os pares da base.")
    top_custo_beneficio: bool = Field(
        default=False, description="Entre os melhores custo-benefício da base.")
    nota_utilidade: float | None = Field(
        default=None, description="Média dos nichos da utilidade pedida (0–100).")
    nota_foco: float | None = Field(
        default=None, description="Nota usada para ordenar conforme o foco (0–100).")
    explicacao: str | None = Field(
        default=None,
        description=("Por que o par foi escolhido: motivo, semelhanças e diferenças com "
                     "exemplos de variáveis, cobertura, logística e previsão."))
    motivos: list[str] = Field(
        default_factory=list, description="Frases curtas para exibir como etiquetas.")


class VariavelPar(BaseModel):
    """Comparação de uma variável entre o local terrestre e o alvo da base."""

    nicho: str
    variavel: str = Field(..., examples=["temperatura__ar_2m_c"])
    nome: str = Field(..., examples=["temperatura média do ar"])
    unidade: str = Field(..., description="Vazia = adimensional; 0/1 = presença/ausência.")
    valor_terra: float | None
    alvo: float
    tolerancia: float
    peso: float
    nota: float | None = Field(..., description="100 × (1 − |valor − alvo| / tolerância).")


class Rota(BaseModel):
    """Base de apoio que atende um local terrestre (principal ou alternativa)."""

    ordem: int = Field(..., description="1 = principal; 2 em diante = alternativas.")
    tipo_rota: Literal["principal", "alternativa"]
    apoio_id: str = Field(..., examples=["NASA-0015"])
    nome: str
    categoria: str
    operador: str
    pais: str
    vinculo: str
    latitude: float
    longitude: float
    distancia_km: float = Field(..., description="Distância em linha reta (grande círculo).")
    prioridade: float = Field(..., description="prioridade_combinada do catálogo (0–1).")
    peso_rota: float


class ParComLocal(Par):
    local: LocalTerra


class ParComBase(Par):
    base: BaseEspacial


class ParCustoBeneficio(Par):
    """Par ranqueado por custo-benefício, com local, base e rotas de apoio."""

    local: LocalTerra
    base: BaseEspacial
    rotas: list[Rota]


class CustoBeneficioResponse(BaseModel):
    items: list[ParCustoBeneficio]
    total: int = Field(..., description="Pares após os filtros, antes da paginação.")
    limit: int
    offset: int
    foco: str
    peso_logistica: float = Field(..., description="Peso efetivo da logística em nota_foco.")
    utilidade: str | None = None


class FocoInfo(BaseModel):
    foco: str = Field(..., examples=["equilibrado"])
    nome: str
    peso_logistica: float
    descricao: str


class UtilidadeInfo(BaseModel):
    utilidade: str = Field(..., examples=["mobilidade"])
    nome: str
    descricao: str
    nichos: list[str]


class FiltrosResponse(BaseModel):
    """Valores aceitos pelos filtros, para montar os seletores do front."""

    focos: list[FocoInfo]
    utilidades: list[UtilidadeInfo]
    nichos: list[Nicho]
    tipos: list[str]
    paises: list[str]
    categorias_apoio: list[str]
    vinculos_apoio: list[str]


class Apoio(BaseModel):
    """Base de apoio da NASA ou de parceiros."""

    apoio_id: str
    nome: str
    categoria: str
    subcategoria: str | None = None
    operador: str
    tipo_operador: str | None = None
    pais: str
    continente: str | None = None
    local: str | None = None
    latitude: float
    longitude: float
    coord_precisao: str | None = None
    capacidades: str | None = None
    programas: str | None = None
    vinculo: str
    status: str | None = None
    relevancia_score: int | None = None
    compatibilidade_score: int | None = None
    prioridade: float
    eua: bool
    usado_na_logistica: bool


class ApoioListResponse(BaseModel):
    items: list[Apoio]
    total: int


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
    rotas: list[Rota] = Field(default_factory=list)


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
    rotas: list[Rota] = Field(default_factory=list)
    variaveis: list[VariavelPar] = Field(
        default_factory=list, description="Valor na Terra × alvo de cada variável do perfil.")
