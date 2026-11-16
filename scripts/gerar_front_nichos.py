"""Gera front-end/src/app/core/nichos.ts a partir de config/nichos.json e config/nomes_locais.json.

O front agrupa as notas por variável (notas_criterios) nos nichos do radar e mostra
região/país dos locais; as duas tabelas vêm daqui para não divergirem da API.

Uso: python scripts/gerar_front_nichos.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "front-end/src/app/core/nichos.ts"


def main() -> None:
    nichos = json.loads((ROOT / "config/nichos.json").read_text(encoding="utf-8"))
    nomes = json.loads((ROOT / "config/nomes_locais.json").read_text(encoding="utf-8"))
    mapa = {corpo: {item["terra"]: nicho for nicho, itens in grupos.items() for item in itens}
            for corpo, grupos in nichos.items()}
    OUT.write_text(
        "// GERADO a partir de config/nichos.json e config/nomes_locais.json.\n"
        "// Regere com: python scripts/gerar_front_nichos.py\n\n"
        "import { Corpo } from './recomendacoes.models';\n\n"
        "/** Nicho de cada variável terrestre, por corpo. */\n"
        "export const NICHO_DA_VARIAVEL: Record<Corpo, Record<string, string>> = "
        f"{json.dumps(mapa, ensure_ascii=False, indent=2)};\n\n"
        '/** Região e país por célula "lat,lon" (Nominatim/OpenStreetMap, ODbL). */\n'
        "export const NOMES_LOCAIS: Record<string, { regiao?: string; pais?: string }> = "
        f"{json.dumps(nomes['locais'], ensure_ascii=False)};\n",
        encoding="utf-8",
    )
    print(OUT)


if __name__ == "__main__":
    main()
