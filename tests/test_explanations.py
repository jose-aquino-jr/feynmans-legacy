"""Testes das explicações em texto dos análogos."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feynmans_legacy.explanations import (
    add_explanations,
    explain_base,
    explain_pair,
    fmt,
    join_pt,
    trend_state,
    utility_scores,
    variable_phrase,
)

VARIABLES = pd.DataFrame({
    "par_id": ["P"] * 4,
    "nicho": ["termico", "geologia", "geologia", "superficie_poeira"],
    "variavel": ["temperatura__ar_2m_c", "geologia_superficie__litologia_basalto",
                 "geologia_superficie__litologia_impacto", "biologia__carbono_organico_solo"],
    "nome": ["temperatura média do ar", "basalto", "estruturas de impacto",
             "carbono orgânico do solo"],
    "unidade": ["°C", "0/1", "0/1", "g/kg"],
    "valor_terra": [28.2, 1.0, 0.0, np.nan],
    "alvo": [-46.3, 1.0, 0.0, 5.0],
    "nota": [20.9, 100.0, 100.0, np.nan],
})
SITE = {"nome": "Deserto da Núbia — Sudão", "distancia_eua_km": 9579.4,
        "apoio_principal_nome": "MBRSC", "distancia_apoio_km": 2315.2, "n_apoios_raio": 1}


def test_number_formatting_is_pt_br() -> None:
    assert fmt(1234.56, 1) == "1.234,6"
    assert fmt(0.5, 2) == "0,50"
    assert join_pt(["a"]) == "a"
    assert join_pt(["a", "b", "c"]) == "a, b e c"


def test_variable_phrase_handles_units_and_presence() -> None:
    temperature, basalt = VARIABLES.iloc[0], VARIABLES.iloc[1]
    assert variable_phrase(temperature) == (
        "temperatura média do ar: 28,2 °C aqui contra -46,3 °C no alvo")
    assert variable_phrase(basalt) == "basalto presente aqui e presente no alvo"


def test_trend_state() -> None:
    assert trend_state(80, 81) == "estável"
    assert trend_state(80, 85) == "alta"
    assert trend_state(80, 70) == "queda"


def test_specialist_pair_explains_reason_strengths_weaknesses_and_logistics() -> None:
    pair = {"tipo": "especialista", "nichos_destaque": "geologia", "nota_geral": 61.0,
            "rank_base": 9, "cobertura": 0.8, "nota_logistica": 7.0,
            "custo_beneficio": 20.7}
    text, reasons = explain_pair(
        pair, "Cratera Jezero", SITE,
        {"geologia": 100.0, "termico": 20.9, "superficie_poeira": 90.0},
        VARIABLES, (84.0, 80.0), 2500.0)
    assert text.startswith("Foi escolhido por ser muito parecido em Geologia (100), "
                           "mesmo com nota geral 61.")
    assert "Também parecido em Superfície e poeira (90)." in text
    assert ("Diferente em Térmico (21), porque temperatura média do ar: 28,2 °C aqui "
            "contra -46,3 °C no alvo.") in text
    assert "Faltam dados de carbono orgânico do solo neste local; a nota usa 80% do perfil." \
        in text
    assert ("Logística fraca (7): 9.579 km da instalação dos EUA mais próxima; apoio "
            "principal em MBRSC, a 2.315 km; 1 base de apoio a até 2.500 km.") in text
    assert "a nota tende a cair nos próximos meses (84 → 80)." in text
    assert reasons == ["Especialista em Geologia", "Forte em Superfície e poeira (90)",
                       "Fraco em Térmico (21)", "Dados parciais", "Logística fraca",
                       "Previsão em queda"]


def test_pair_without_scores_or_logistics_still_explains() -> None:
    pair = {"tipo": "geral", "nichos_destaque": "", "nota_geral": np.nan, "rank_base": 3,
            "cobertura": 1.0, "nota_logistica": np.nan}
    text, reasons = explain_pair(pair, "Gale", {"nome": "X"}, {}, VARIABLES.iloc[0:0],
                                 None, 2500.0)
    assert text == ("Está entre as melhores notas gerais para Gale: 3º lugar, sem nota "
                    "geral (dados insuficientes no perfil completo).")
    assert reasons == ["Top 3 em semelhança"]


def test_uninformative_zero_example_is_skipped() -> None:
    pair = {"tipo": "destaque", "nichos_destaque": "", "nota_geral": 90.0, "rank_base": 1,
            "cobertura": 1.0}
    zeros = VARIABLES[VARIABLES["variavel"].str.endswith("impacto")]
    text, _ = explain_pair(pair, "Base", {"nome": "Lugar"}, {"geologia": 100.0}, zeros,
                           None, 2500.0)
    assert "Exemplo" not in text


def test_utility_scores_average_available_niches() -> None:
    scores = utility_scores({"geologia": 90.0, "terreno": 70.0, "superficie_poeira": np.nan})
    assert scores["geologia"] == 80.0
    assert scores["tubos_lava"] == 80.0
    # habitat has only one niche with data (terreno), so it is not scored.
    assert "habitat" not in scores


def test_base_summary_names_easy_and_hard_niches() -> None:
    base = {"nome": "Cratera Jezero", "n_pares": 2, "melhor_location_id": "T1",
            "melhor_nota": 83.9, "melhor_custo_beneficio_location_id": "T2",
            "melhor_custo_beneficio": 84.7}
    medians = pd.Series({"agua_gelo": 100.0, "atmosfera": 0.0, "termico": 28.0,
                         "geologia": 80.0})
    text = explain_base(base, medians, {"T1": "Núbia", "T2": "Califórnia, EUA"})
    assert text == ("Cratera Jezero: 2 análogos na Terra. Mais parecido: Núbia (nota 84). "
                    "Melhor custo-benefício: Califórnia, EUA (85). Na Terra é mais fácil "
                    "reproduzir Água e gelo (100) e Geologia (80). O mais difícil é "
                    "Atmosfera (0) e Térmico (28) (mediana entre os análogos).")


def test_add_explanations_fills_every_table() -> None:
    tables = {
        "bases": pd.DataFrame({"base_id": ["B"], "nome": ["Base"], "n_pares": [1],
                               "melhor_location_id": ["T"], "melhor_nota": [80.0]}),
        "locais": pd.DataFrame({"location_id": ["T"], "nome": ["Lugar"],
                                "nota_logistica": [50.0], "temperatura_media_c": [10.0]}),
        "pares": pd.DataFrame({"par_id": ["P"], "base_id": ["B"], "location_id": ["T"],
                               "tipo": ["geral"], "nichos_destaque": [""], "rank_base": [1],
                               "nota_geral": [80.0], "cobertura": [1.0],
                               "nota_logistica": [50.0], "custo_beneficio": [63.2]}),
        "pares_nichos": pd.DataFrame({"par_id": ["P", "P"], "base_id": ["B", "B"],
                                      "nicho": ["geologia", "terreno"],
                                      "nota": [90.0, 80.0]}),
        "pares_variaveis": VARIABLES.assign(par_id="P"),
        "series": pd.DataFrame({"par_id": ["P", "P"], "anomes": [202608, 202609],
                                "origem": ["observada", "prevista"], "nota": [80.0, 80.5],
                                "cobertura": [1.0, 1.0]}),
    }
    add_explanations(tables, raio_rotas_km=2500.0)
    assert tables["pares"]["explicacao"].iloc[0].startswith("Está entre as melhores")
    assert tables["pares"]["motivos"].iloc[0].split("\n")[-1] == "Previsão estável"
    assert tables["locais"]["usos_recomendados"].iloc[0] == "geologia,tubos_lava"
    assert "Mais útil para Geologia e amostras (85)" in tables["locais"]["explicacao"].iloc[0]
    assert tables["bases"]["explicacao"].iloc[0].startswith("Base: 1 análogos na Terra.")


def test_terrestrial_equivalent_target_is_flagged() -> None:
    row = {"nome": "poeira no ar", "unidade": "µg/m³", "valor_terra": 6.9, "alvo": 89.6,
           "tipo_alvo": "equivalente terrestre"}
    assert variable_phrase(row) == (
        "poeira no ar: 6,90 µg/m³ aqui contra 89,6 µg/m³ no alvo (equivalente terrestre)")
