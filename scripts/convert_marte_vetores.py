"""Converte os vetores geologicos de Marte para GeoPackage.

Fontes:
- Mapa geologico global 1:15M (USGS/Astropedia, shapefiles Mars 2000 Sphere).
- SIM 3464 - banco de dados geologico de Jezero/Nili (FileGDB, MTM 77.5E).

Usa a API de baixo nivel do pyogrio (sem depender de geopandas).
"""

from __future__ import annotations

import tempfile
import warnings
import zipfile
from pathlib import Path

import pyogrio.raw as ogr

warnings.filterwarnings("ignore", category=RuntimeWarning)

BASE = Path(__file__).resolve().parents[1] / "data" / "marte" / "geologia"


def copiar_camada(
    origem: Path,
    destino: Path,
    camada: str,
    camada_origem: str | None = None,
) -> None:
    meta, _, geometria, atributos = ogr.read(origem, layer=camada_origem or camada)
    ogr.write(
        destino,
        geometria,
        atributos,
        fields=meta["fields"],
        crs=meta["crs"],
        geometry_type=meta["geometry_type"],
        driver="GPKG",
        layer=camada,
        append=destino.exists(),
    )
    print(f"[ok] {destino.name}::{camada} ({len(geometria)} feicoes)")


def converter_15m() -> None:
    origem_zip = BASE / "mars_15m_geologic_gis.zip"
    destino = BASE / "mars_global_geology_15m.gpkg"
    destino.unlink(missing_ok=True)

    camadas = {
        "geo_units_oc_dd": "unidades_geologicas",
        "geo_contacts_oc_dd": "contatos_geologicos",
        "geo_structure_oc_dd": "estruturas",
        "Type_Localities_oc_dd": "localidades_tipo",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(origem_zip) as z:
            for nome in z.namelist():
                if Path(nome).suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                    z.extract(nome, tmp_path)

        pasta = (
            tmp_path
            / "I1802ABC_Mars_global_geology"
            / "Shapefiles"
            / "I1802ABC_Mars2000_Sphere"
        )
        for arquivo, camada in camadas.items():
            origem = pasta / f"{arquivo}.shp"
            if not origem.exists():
                print(f"[aviso] ausente: {origem.name}")
                continue
            copiar_camada(origem, destino, camada, camada_origem=arquivo)

    print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


def converter_sim3464() -> None:
    origem = BASE / "sim3464" / "sim3464_JezeroNili_FINAL" / "Geodatabase" / "Nili.gdb"
    destino = BASE / "jezero_nili_geology.gpkg"
    destino.unlink(missing_ok=True)

    camadas = [
        "GeoUnits_v1",
        "GeoContacts",
        "SurfaceFeatures",
        "LinearFeatures",
        "LocationFeatures",
        "LandingEllipse",
        "Nomenclature",
        "MapBoundary",
    ]

    for camada in camadas:
        copiar_camada(origem, destino, camada)

    print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


if __name__ == "__main__":
    converter_15m()
    converter_sim3464()
