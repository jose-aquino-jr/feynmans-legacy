"""Leitura dos análogos gerados em ``data/tratados/analogos/``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings
from app.schemas.analogos import (
    Apoio,
    ApoioListResponse,
    BaseDetalhe,
    BaseEspacial,
    BaseListResponse,
    CustoBeneficioResponse,
    LocalDetalhe,
    LocalListResponse,
    LocalTerra,
    Nicho,
    NichoListResponse,
    Par,
    ParComBase,
    ParComLocal,
    ParCustoBeneficio,
    ParDetalhe,
    PontoSerie,
    Rota,
)
from app.services.cache import BoundedCache
from app.services.dataframe import frame_to_records
from app.services.errors import ApiError

logger = logging.getLogger("feynmans_legacy.api.analogos")

ANALOG_DIR = "analogos"
LIST_COLUMNS = ("nichos_destaque", "pontos_fortes", "pontos_fracos")
NICHE_LABELS = {
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


def _split(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item for item in value.split(",") if item]


class AnalogRepository:
    """Monta as respostas do mapa 3D a partir das tabelas de análogos."""

    def __init__(self, settings: Settings) -> None:
        self.root = settings.data_dir / ANALOG_DIR
        self._cache: BoundedCache[tuple[str, int, int], pd.DataFrame] = BoundedCache(16)

    # ------------------------------------------------------------------ loading
    def _table(self, name: str) -> pd.DataFrame:
        path = self.root / f"{name}.parquet"
        try:
            stat = path.stat()
        except OSError as exc:
            raise ApiError(
                404,
                "analogs_not_generated",
                "Os análogos ainda não foram gerados; rode scripts/gerar_analogos.py.",
                {"arquivo": f"{ANALOG_DIR}/{name}.parquet"},
            ) from exc
        key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        try:
            return self._cache.get_or_load(key, lambda: _read(path))
        except Exception as exc:
            logger.exception("analogs_load_failed", extra={"file": path.as_posix()})
            raise ApiError(
                500,
                "analogs_read_error",
                f"Não foi possível ler {ANALOG_DIR}/{name}.parquet.",
                {"arquivo": f"{ANALOG_DIR}/{name}.parquet"},
            ) from exc

    def _optional_table(self, name: str) -> pd.DataFrame | None:
        """Tables added later (rotas, apoios) may be absent in older outputs."""
        if not (self.root / f"{name}.parquet").is_file():
            return None
        return self._table(name)

    def _routes(self, location_ids: list[str]) -> dict[str, list[Rota]]:
        frame = self._optional_table("rotas")
        if frame is None:
            return {}
        frame = frame[frame["location_id"].isin(location_ids)].sort_values(
            ["location_id", "ordem"])
        routes: dict[str, list[Rota]] = {}
        for record in frame_to_records(frame):
            routes.setdefault(str(record["location_id"]), []).append(
                Rota.model_validate(record))
        return routes

    def _bases(self) -> dict[str, BaseEspacial]:
        frame = self._table("bases")
        return {
            str(record["base_id"]): BaseEspacial.model_validate(record)
            for record in frame_to_records(frame)
        }

    def _sites(self) -> dict[str, LocalTerra]:
        frame = self._table("locais")
        return {
            str(record["location_id"]): LocalTerra.model_validate(record)
            for record in frame_to_records(frame)
        }

    def _pairs(self, frame: pd.DataFrame) -> list[Par]:
        niches = self._table("pares_nichos")
        scores = niches[niches["par_id"].isin(frame["par_id"])]
        by_pair: dict[str, dict[str, float | None]] = {}
        for record in frame_to_records(scores[["par_id", "nicho", "nota"]]):
            by_pair.setdefault(str(record["par_id"]), {})[str(record["nicho"])] = record["nota"]
        pairs = []
        for record in frame_to_records(frame):
            for column in LIST_COLUMNS:
                record[column] = _split(record.get(column))
            record["nichos"] = by_pair.get(str(record["par_id"]), {})
            pairs.append(Par.model_validate(record))
        return pairs

    # ------------------------------------------------------------------ nichos
    def list_niches(self) -> NichoListResponse:
        frame = self._table("pares_nichos")[["nicho", "corpo"]].drop_duplicates()
        bodies = frame.groupby("nicho", sort=False)["corpo"].agg(lambda s: sorted(set(s)))
        items = [
            Nicho(nicho=str(niche), nome=NICHE_LABELS.get(str(niche), str(niche)),
                  corpos=list(corpos))
            for niche, corpos in bodies.items()
        ]
        return NichoListResponse(items=items, total=len(items))

    # ------------------------------------------------------------------- bases
    def list_bases(self, corpo: str | None) -> BaseListResponse:
        items = [base for base in self._bases().values() if corpo in (None, base.corpo)]
        return BaseListResponse(items=items, total=len(items))

    def get_base(
        self,
        base_id: str,
        *,
        tipo: str | None,
        destaque: bool | None,
        forte_em: str | None,
        nota_minima: float | None,
        limit: int,
        ordenar: str = "nota",
    ) -> BaseDetalhe:
        base = self._bases().get(base_id)
        if base is None:
            raise ApiError(404, "base_not_found", f"A base '{base_id}' não existe.",
                           {"base_id": base_id})
        frame = self._table("pares")
        frame = frame[frame["base_id"] == base_id]
        if tipo is not None:
            frame = frame[frame["tipo"] == tipo]
        if destaque is not None:
            frame = frame[frame["destaque"] == destaque]
        if nota_minima is not None:
            frame = frame[frame["nota_geral"] >= nota_minima]
        if forte_em is not None:
            strong = frame["pontos_fortes"].map(_split).map(lambda items: forte_em in items)
            chosen = frame["nichos_destaque"].map(_split).map(lambda items: forte_em in items)
            frame = frame[strong | chosen]
        if ordenar == "custo_beneficio" and "custo_beneficio" in frame.columns:
            frame = frame.sort_values("custo_beneficio", ascending=False, na_position="last")
        else:
            frame = frame.sort_values("rank_base")
        sites = self._sites()
        pairs = [
            ParComLocal(**pair.model_dump(), local=sites[pair.location_id])
            for pair in self._pairs(frame.head(limit))
        ]
        return BaseDetalhe(base=base, pares=pairs, total=len(frame))

    # ------------------------------------------------------------------ locais
    def list_sites(
        self, *, destaque: bool | None, pais: str | None, limit: int, offset: int
    ) -> LocalListResponse:
        items = [
            site for site in self._sites().values()
            if destaque in (None, site.destaque)
            and (pais is None or (site.pais or "").casefold() == pais.casefold())
        ]
        return LocalListResponse(items=items[offset: offset + limit], total=len(items),
                                 limit=limit, offset=offset)

    def get_site(self, location_id: str) -> LocalDetalhe:
        site = self._sites().get(location_id)
        if site is None:
            raise ApiError(404, "local_not_found",
                           f"O local '{location_id}' não tem análogos.",
                           {"location_id": location_id})
        frame = self._table("pares")
        frame = frame[frame["location_id"] == location_id].sort_values(
            "nota_geral", ascending=False, na_position="last")
        bases = self._bases()
        pairs = [ParComBase(**pair.model_dump(), base=bases[pair.base_id])
                 for pair in self._pairs(frame)]
        return LocalDetalhe(local=site, pares=pairs,
                            rotas=self._routes([location_id]).get(location_id, []))

    # ---------------------------------------------------------- custo-benefício
    def list_cost_benefit(
        self, *, corpo: str | None, base_id: str | None, apenas_top: bool, limit: int
    ) -> CustoBeneficioResponse:
        frame = self._table("pares")
        if "custo_beneficio" not in frame.columns:
            raise ApiError(404, "cost_benefit_not_generated",
                           "Os análogos foram gerados sem o catálogo de bases de apoio.",
                           {"arquivo": "data/terra/apoio/nasa_bases_suporte.parquet"})
        if base_id is not None and base_id not in self._bases():
            raise ApiError(404, "base_not_found", f"A base '{base_id}' não existe.",
                           {"base_id": base_id})
        frame = frame.dropna(subset=["custo_beneficio"])
        if corpo is not None:
            frame = frame[frame["corpo"] == corpo]
        if base_id is not None:
            frame = frame[frame["base_id"] == base_id]
        if apenas_top:
            frame = frame[frame["top_custo_beneficio"].astype(bool)]
        frame = frame.sort_values(["custo_beneficio", "par_id"], ascending=[False, True])
        page = self._pairs(frame.head(limit))
        sites, bases = self._sites(), self._bases()
        routes = self._routes([pair.location_id for pair in page])
        items = [
            ParCustoBeneficio(**pair.model_dump(), local=sites[pair.location_id],
                              base=bases[pair.base_id],
                              rotas=routes.get(pair.location_id, []))
            for pair in page
        ]
        return CustoBeneficioResponse(items=items, total=len(frame))

    def list_support(
        self, *, eua: bool | None, usado: bool | None, categoria: str | None
    ) -> ApoioListResponse:
        frame = self._optional_table("apoios")
        if frame is None:
            raise ApiError(404, "support_not_generated",
                           "O catálogo de bases de apoio não foi publicado.",
                           {"arquivo": f"{ANALOG_DIR}/apoios.parquet"})
        if eua is not None:
            frame = frame[frame["eua"] == eua]
        if usado is not None:
            frame = frame[frame["usado_na_logistica"] == usado]
        if categoria is not None:
            frame = frame[frame["categoria"].str.casefold() == categoria.casefold()]
        items = [Apoio.model_validate(record) for record in frame_to_records(frame)]
        return ApoioListResponse(items=items, total=len(items))

    # -------------------------------------------------------------------- pares
    def get_pair(self, par_id: str) -> ParDetalhe:
        frame = self._table("pares")
        frame = frame[frame["par_id"] == par_id]
        if frame.empty:
            raise ApiError(404, "pair_not_found", f"O par '{par_id}' não existe.",
                           {"par_id": par_id})
        pair = self._pairs(frame)[0]
        series = self._table("series")
        points = [PontoSerie.model_validate(record) for record in frame_to_records(
            series[series["par_id"] == par_id].sort_values("anomes")[
                ["anomes", "origem", "nota", "cobertura"]])]
        return ParDetalhe(par=pair, base=self._bases()[pair.base_id],
                          local=self._sites()[pair.location_id], serie=points,
                          rotas=self._routes([pair.location_id]).get(pair.location_id, []))


def _read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
