"""Converte produtos PDS/ENVI de Marte para GeoTIFF.

Os dados brutos ficam em ``data/marte`` (ver ``data/README.md``). Este script
gera versoes GeoTIFF prontas para uso em SIG a partir dos formatos PDS3 IMG,
ENVI e tabelas ASCII.

Uso:
    python scripts/convert_marte.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

RAIO_MARTE = 3_396_190.0  # esfera Mars 2000 (IAU 2000), em metros

# Projecao equirretangular centrada no meridiano 0, com longitudes 0-360.
CRS_0_360 = (
    f"+proj=eqc +lat_ts=0 +lon_0=0 +a={RAIO_MARTE} +b={RAIO_MARTE} +units=m +no_defs"
)

BASE = Path(__file__).resolve().parents[1] / "data" / "marte"


def escrever(
    destino: Path,
    dados: np.ndarray,
    transform,
    crs: str,
    *,
    nodata=None,
    dtype: str = "int16",
    descricao: str = "",
    unidade: str = "",
) -> None:
    """Grava um array 2D como GeoTIFF de uma banda."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    perfil = {
        "driver": "GTiff",
        "height": dados.shape[0],
        "width": dados.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if nodata is not None:
        perfil["nodata"] = nodata
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(dados.astype(dtype), 1)
        if descricao:
            dst.update_tags(1, DESCRICAO=descricao)
        if unidade:
            dst.update_tags(1, UNIDADE=unidade)
        dst.update_tags(FONTE="NASA/PDS", ESFERA=f"raio {RAIO_MARTE:.0f} m")


def eqc_transform(
    width: int,
    height: int,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
):
    """Transform afim para projecao equirretangular em metros."""
    x_min = math.radians(lon_min) * RAIO_MARTE
    x_max = math.radians(lon_max) * RAIO_MARTE
    y_min = math.radians(lat_min) * RAIO_MARTE
    y_max = math.radians(lat_max) * RAIO_MARTE
    return from_bounds(x_min, y_min, x_max, y_max, width, height)


# ---------------------------------------------------------------------------
# MOLA MEGDR 1/16 grau
# ---------------------------------------------------------------------------
def converter_mola() -> None:
    origem = BASE / "topografia" / "mola_megt90n000eb.img"
    destino = BASE / "topografia" / "mola_topo_global_1_16deg.tif"
    linhas, colunas = 2880, 5760
    dados = np.fromfile(origem, dtype=">i2").reshape(linhas, colunas)
    transform = eqc_transform(colunas, linhas, 0.0, 360.0, -90.0, 90.0)
    escrever(
        destino,
        dados,
        transform,
        CRS_0_360,
        descricao="Topografia MOLA (mediana por celula de 1/16 grau) relativa ao areoide GMM3",
        unidade="metro",
    )
    print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


# ---------------------------------------------------------------------------
# TES thermal inertia (dia/noite)
# ---------------------------------------------------------------------------
def converter_tes() -> None:
    dados_dir = BASE / "ambiente_recursos" / "tes_timap" / "mgst_9001" / "data"
    for periodo in ("day", "night"):
        origem = dados_dir / f"global_ti_{periodo}_2007.img"
        destino = BASE / "ambiente_recursos" / f"tes_ti_{periodo}_global.tif"
        linhas, colunas = 3600, 7200
        dados = np.fromfile(origem, dtype=">i2").reshape(linhas, colunas)
        # A fonte usa longitude -180..180; rola para 0..360 para padronizar
        # com MOLA, CRISM e GRS (todos em 0..360, leste positivo).
        dados = np.roll(dados, -colunas // 2, axis=1)
        transform = eqc_transform(colunas, linhas, 0.0, 360.0, -90.0, 90.0)
        escrever(
            destino,
            dados,
            transform,
            CRS_0_360,
            descricao=f"Inercia termica TES ({'diurna' if periodo == 'day' else 'noturna'}), 2007",
            unidade="J/(m^2*K*sqrt(s))",
        )
        print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


# ---------------------------------------------------------------------------
# CRISM map-projected summary products (ENVI -> GeoTIFF)
# ---------------------------------------------------------------------------
def converter_crism() -> None:
    for origem in sorted((BASE / "geologia").glob("crism_jezero_*_20n073.img")):
        destino = origem.with_suffix(".tif")
        with rasterio.open(origem) as src:
            dados = src.read()
            perfil = {
                "driver": "GTiff",
                "height": src.height,
                "width": src.width,
                "count": src.count,
                "dtype": src.dtypes[0],
                "crs": src.crs,
                "transform": src.transform,
                "compress": "deflate",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
            }
            if src.nodata is not None:
                perfil["nodata"] = src.nodata
        with rasterio.open(destino, "w", **perfil) as dst:
            dst.write(dados)
            dst.update_tags(FONTE="NASA/PDS CRISM MRDR", ESFERA=f"raio {RAIO_MARTE:.0f} m")
        print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


# ---------------------------------------------------------------------------
# GRS: concentracoes elementares (grade de 5 graus)
# ---------------------------------------------------------------------------
def converter_grs_elementos() -> None:
    elementos = ["h2o", "cl", "fe", "si", "k", "th"]
    n_lat, n_lon = 36, 72
    for elemento in elementos:
        origem = BASE / "ambiente_recursos" / f"grs_{elemento}_sr_5x5.tab"
        destino = BASE / "ambiente_recursos" / f"grs_{elemento}_5deg.tif"
        valores = np.full(n_lat * n_lon, np.nan, dtype="float32")
        with origem.open() as fh:
            for linha in fh:
                partes = linha.split()
                if len(partes) < 3:
                    continue
                lat, lon, concentracao = map(float, partes[:3])
                if concentracao >= 9999.0:
                    continue
                col = int(round((lon - 2.5) / 5.0))
                row = int(round((87.5 - lat) / 5.0))
                valores[row * n_lon + col] = concentracao
        dados = valores.reshape(n_lat, n_lon)
        transform = eqc_transform(n_lon, n_lat, 0.0, 360.0, -90.0, 90.0)
        unidade = "ppm (partes por milhao)" if elemento == "th" else "percentual em massa"
        escrever(
            destino,
            dados,
            transform,
            CRS_0_360,
            nodata=np.nan,
            dtype="float32",
            descricao=(
                f"Concentracao de {elemento.upper()} medida pelo GRS "
                "(grade de 5 graus, suavizada)"
            ),
            unidade=unidade,
        )
        print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


# ---------------------------------------------------------------------------
# GRS: fluxo de neutrons (grade de 0.5 grau)
# ---------------------------------------------------------------------------
def converter_grs_neutrons() -> None:
    tipos = ["epithermal", "thermal", "fast"]
    n_lat, n_lon = 360, 720
    for tipo in tipos:
        origem = BASE / "ambiente_recursos" / f"grs_ns_{tipo}_020917.tab"
        destino = BASE / "ambiente_recursos" / f"grs_ns_{tipo}.tif"
        valores = np.zeros(n_lat * n_lon, dtype="float32")
        with origem.open() as fh:
            for linha in fh:
                partes = linha.replace(",", " ").split()
                if len(partes) < 3:
                    continue
                lon, lat, fluxo = map(float, partes[:3])
                col = int(round((lon - 0.25) / 0.5))
                row = int(round((89.75 - lat) / 0.5))
                if 0 <= row < n_lat and 0 <= col < n_lon:
                    valores[row * n_lon + col] = fluxo
        dados = valores.reshape(n_lat, n_lon)
        transform = eqc_transform(n_lon, n_lat, 0.0, 360.0, -90.0, 90.0)
        escrever(
            destino,
            dados,
            transform,
            CRS_0_360,
            dtype="float32",
            descricao=(
                f"Fluxo de neutrons {tipo} medido pelo GRS/NS "
                "(0.5 grau, primeiros 25.7 dias de mapeamento)"
            ),
            unidade="contagens/segundo",
        )
        print(f"[ok] {destino.relative_to(BASE.parent.parent)}")


def principal() -> None:
    converter_mola()
    converter_tes()
    converter_crism()
    converter_grs_elementos()
    converter_grs_neutrons()


if __name__ == "__main__":
    principal()
