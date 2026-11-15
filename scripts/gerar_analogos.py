"""Gera os pares Terra ↔ Lua/Marte servidos pela API em data/tratados/analogos/.

Uso (na raiz do projeto, depois dos notebooks 01 e 02):

    python scripts/gerar_analogos.py

Para dar nome aos locais novos, rode depois ``python scripts/nomear_locais.py``
e gere de novo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feynmans_legacy.analog_pairs import generate  # noqa: E402


def main() -> None:
    out_dir = ROOT / "data/tratados/analogos"
    tables = generate(ROOT, out_dir)
    pairs, sites = tables["pares"], tables["locais"]
    print(f"{len(tables['bases'])} bases, {len(sites)} locais terrestres, {len(pairs)} pares")
    print(pairs["tipo"].value_counts().to_string())
    unnamed = sites["pais"].isna()
    if unnamed.any():
        print(f"{int(unnamed.sum())} locais sem nome; rode scripts/nomear_locais.py")
    print(f"Arquivos em {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
