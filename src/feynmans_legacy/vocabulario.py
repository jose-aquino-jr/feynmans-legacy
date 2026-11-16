"""Nomes legíveis de nichos, variáveis e utilidades (compartilhados com a API)."""

from __future__ import annotations

from typing import TypedDict


class UtilityInfo(TypedDict):
    nome: str
    descricao: str
    nichos: tuple[str, ...]

NICHE_LABELS: dict[str, str] = {
    "termico": "Térmico",
    "iluminacao_radiacao": "Iluminação e radiação",
    "agua_gelo": "Água e gelo",
    "agua_aridez": "Água e aridez",
    "terreno": "Terreno",
    "geologia": "Geologia",
    "superficie_poeira": "Superfície e poeira",
    "processos": "Processos de vento e poeira",
    "biologia_habitabilidade": "Biologia e habitabilidade",
    "subsuperficie": "Subsuperfície",
    "atmosfera": "Atmosfera",
    "operacoes": "Operações",
}

# coluna terrestre -> (nome curto, unidade). Unidade vazia = adimensional.
# Unidade "0/1" marca presença/ausência.
VARIABLES: dict[str, tuple[str, str]] = {
    "temperatura__ar_2m_c": ("temperatura média do ar", "°C"),
    "temperatura__lst_amplitude_dia_noite_c": ("diferença de temperatura dia-noite", "°C"),
    "iluminacao_radiacao__radiacao_solar_superficie_wm2": ("radiação solar", "W/m²"),
    "iluminacao_radiacao__elevacao_solar_max_graus": ("altura máxima do sol", "°"),
    "iluminacao_radiacao__dias_dia_polar": ("dias de sol 24 h por ano", "dias"),
    "agua_gelo__precipitacao_mm_dia": ("chuva", "mm/dia"),
    "agua_gelo__umidade_solo_raiz_m3m3": ("umidade do solo", "m³/m³"),
    "agua_gelo__indice_permafrost": ("índice de solo congelado", ""),
    "subsuperficie__solo_congelado_indice": ("gelo subterrâneo", ""),
    "subsuperficie__potencial_tubos_lava": ("potencial de tubos de lava", ""),
    "relevo__amplitude_relevo_m": ("amplitude do relevo", "m"),
    "relevo__indice_posicao_topografica_m": ("posição topográfica", "m"),
    "relevo__declividade_media_graus": ("declividade média", "°"),
    "relevo__elevacao_media_m": ("altitude média", "m"),
    "geologia_superficie__litologia_anortosito": ("rocha anortosito", "0/1"),
    "geologia_superficie__litologia_basalto": ("basalto", "0/1"),
    "geologia_superficie__litologia_carbonato": ("carbonatos", "0/1"),
    "geologia_superficie__litologia_eolico": ("depósitos eólicos", "0/1"),
    "geologia_superficie__litologia_evaporito": ("evaporitos (sais)", "0/1"),
    "geologia_superficie__litologia_glacial": ("depósitos glaciais", "0/1"),
    "geologia_superficie__litologia_hidrotermal_ferro": ("depósitos hidrotermais de ferro", "0/1"),
    "geologia_superficie__litologia_impacto": ("estruturas de impacto", "0/1"),
    "geologia_superficie__litologia_lacustre_argila": ("argilas de lago", "0/1"),
    "geologia_superficie__litologia_piroclastico": ("rochas piroclásticas", "0/1"),
    "geologia_superficie__albedo": ("albedo", ""),
    "geologia_superficie__ph": ("pH do solo", ""),
    "biologia__ndvi": ("vegetação (NDVI)", ""),
    "biologia__carbono_organico_solo": ("carbono orgânico do solo", "g/kg"),
    "biologia__cobertura_solo_exposto_arido_fracao": ("fração de solo exposto", ""),
    "poeira_vento_processos__vento_superficie_ms": ("vento", "m/s"),
    "poeira_vento_processos__poeira_superficie_ugm3": ("poeira no ar", "µg/m³"),
    "poeira_vento_processos__pressao_estimada_altitude_kpa": ("pressão atmosférica", "kPa"),
    "operacoes__densidade_populacional": ("densidade populacional", "hab/km²"),
    "operacoes__fracao_terreno_plano_lt5graus": ("fração de terreno plano", ""),
}

UTILITIES: dict[str, UtilityInfo] = {
    "habitat": {
        "nome": "Habitat e base tripulada",
        "descricao": "Clima, luz, terreno plano e abrigo para testar módulos habitáveis.",
        "nichos": ("termico", "iluminacao_radiacao", "operacoes", "subsuperficie", "terreno"),
    },
    "mobilidade": {
        "nome": "Rover e mobilidade",
        "descricao": "Terreno, poeira e solo para testar rodas, navegação e caminhadas (EVA).",
        "nichos": ("terreno", "superficie_poeira", "operacoes", "processos"),
    },
    "geologia": {
        "nome": "Geologia e amostras",
        "descricao": "Rochas e superfície parecidas para treinar coleta e instrumentos.",
        "nichos": ("geologia", "superficie_poeira", "terreno"),
    },
    "agua_recursos": {
        "nome": "Água e recursos (ISRU)",
        "descricao": "Gelo, solo congelado e aridez para testar extração de água.",
        "nichos": ("agua_gelo", "subsuperficie", "agua_aridez"),
    },
    "astrobiologia": {
        "nome": "Astrobiologia",
        "descricao": "Limites da vida: aridez, pouca vegetação e química do solo.",
        "nichos": ("biologia_habitabilidade", "agua_aridez", "superficie_poeira", "geologia"),
    },
    "clima_extremo": {
        "nome": "Treino em clima extremo",
        "descricao": "Frio, calor, radiação e vento para treinar equipes e testar equipamentos.",
        "nichos": ("termico", "iluminacao_radiacao", "processos", "atmosfera"),
    },
    "tubos_lava": {
        "nome": "Cavernas e tubos de lava",
        "descricao": "Subsuperfície e geologia vulcânica para explorar cavernas.",
        "nichos": ("subsuperficie", "geologia", "terreno"),
    },
}


def niche_label(niche: str) -> str:
    return NICHE_LABELS.get(niche, niche)


def variable_label(column: str) -> tuple[str, str]:
    return VARIABLES.get(column, (column, ""))
