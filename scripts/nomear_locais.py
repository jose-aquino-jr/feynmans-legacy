"""Preenche config/nomes_locais.json com região e país dos locais terrestres.

Usa o geocodificador reverso do OpenStreetMap (Nominatim), uma requisição por
segundo, e só consulta coordenadas que ainda não estão no arquivo. Depois rode
``python scripts/gerar_analogos.py`` de novo para aplicar os nomes.

Dados de nomes: © colaboradores do OpenStreetMap, licença ODbL.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from feynmans_legacy.analog_pairs import name_key  # noqa: E402

NAMES = ROOT / "config/nomes_locais.json"
SITES = ROOT / "data/tratados/analogos/locais.parquet"
URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "feynmans-legacy-analogos/1.0"}


def reverse(latitude: float, longitude: float) -> dict[str, str]:
    query = urllib.parse.urlencode({
        "lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 6,
        "accept-language": "pt-BR,pt,en",
    })
    request = urllib.request.Request(f"{URL}?{query}", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: dict[str, Any] = json.load(response)
    address: dict[str, str] = payload.get("address", {})
    region = (address.get("state") or address.get("region") or address.get("province")
              or address.get("county") or address.get("archipelago"))
    return {key: value for key, value in
            {"regiao": region, "pais": address.get("country")}.items() if value}


def main() -> None:
    stored: dict[str, Any] = (json.loads(NAMES.read_text(encoding="utf-8"))
                              if NAMES.is_file() else {})
    names: dict[str, dict[str, str]] = stored.get("locais", {})
    sites = pd.read_parquet(SITES, columns=["latitude", "longitude"])
    pending = [(lat, lon) for lat, lon in sites.itertuples(index=False)
               if name_key(lat, lon) not in names and lat > -60]
    print(f"{len(pending)} coordenadas para consultar")
    for index, (lat, lon) in enumerate(pending, start=1):
        names[name_key(lat, lon)] = reverse(lat, lon)
        print(f"[{index}/{len(pending)}] {lat:.2f},{lon:.2f} -> {names[name_key(lat, lon)]}")
        time.sleep(1.1)
    NAMES.write_text(json.dumps({
        "_fonte": "Nominatim/OpenStreetMap (© colaboradores do OpenStreetMap, ODbL)",
        "locais": dict(sorted(names.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
