"""Recomendações temporais: estado da Terra no AAAAMM + top K por base.

Fluxo de uma consulta:

1. resolve o estado terrestre do mês: observado (até o corte), projeção recursiva
   em disco (``cache_projecoes/<trajetória>/``) ou cenário sazonal (modo ``auto``
   além dos horizontes diretos, ou ``sazonal``);
2. se a projeção recursiva ainda não chegou ao mês, enfileira (ou estende) a tarefa
   e responde 202 com progresso real em meses;
3. com o estado pronto, aplica ``analog_study.recommend`` por base e nicho e pagina
   o ranking de cada base.

Um único worker projeta a trajetória da publicação; retomar após restart usa os
meses já gravados (checkpoints mensais atômicos).
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from app.config import Settings
from app.schemas.recommendations import (
    BaseOpcao,
    Calculando,
    Candidato,
    Criterio,
    GrupoBase,
    OpcoesResponse,
    Publicacao,
    RecomendacoesResponse,
)
from app.services.errors import ApiError
from feynmans_legacy.analog_pairs import load_target_info
from feynmans_legacy.analog_study import KEY, MIN_COVERAGE, profile_criteria, recommend
from feynmans_legacy.forecast_projection import (
    ALGORITHM_VERSION,
    SCHEMA_VERSION,
    WINDOW_MONTHS,
    ProjectionBundle,
    TrajectoryStore,
    file_sha256,
    load_bundle,
    observed_window,
    origin_for,
    period,
    project_until,
    seasonal_base,
    to_anomes,
    trajectory_key,
)
from feynmans_legacy.vocabulario import variable_label

logger = logging.getLogger("feynmans_legacy.api.recomendacoes")

TODOS = "Todos"
BODIES = ("lua", "marte")
FAILURE_TTL_SECONDS = 60.0


class LRU[KeyT: Hashable, ValueT]:
    def __init__(self, size: int) -> None:
        self.size = size
        self.items: OrderedDict[KeyT, ValueT] = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: KeyT, loader: Callable[[], ValueT]) -> ValueT:
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                self.hits += 1
                return self.items[key]
            self.misses += 1
        value = loader()
        with self.lock:
            self.items[key] = value
            while len(self.items) > self.size:
                self.items.popitem(last=False)
        return value


@dataclass
class Job:
    id: str
    target: pd.Period
    status: str = "fila"
    done: int = 0
    total: int = 0
    error: str | None = None
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None


@dataclass
class Snapshot:
    frame: pd.DataFrame
    origem: str
    estrategia: str
    horizonte: int
    mes_base: int | None
    metodos: dict[str, str]
    key: tuple[str, int]


class Publication:
    """Arquivos de uma publicação (carregados uma vez por processo)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        config = settings.recomendacoes_config_dir
        self.niches_path = config / "nichos.json"
        self.niches: dict[str, dict[str, Any]] = json.loads(
            self.niches_path.read_text(encoding="utf-8"))
        raw_bases = json.loads((config / "bases_espaciais.json").read_text(encoding="utf-8"))
        self.base_geometry = {k: v for k, v in raw_bases.items() if not k.startswith("_")}
        self.references = {
            body: pd.read_parquet(settings.recomendacoes_perfis_dir / body / f"{body}.parquet")
            for body in BODIES
        }
        self.target_info = load_target_info(config.parent)
        run = settings.recomendacoes_run_dir
        coords = pd.read_parquet(run / "coordenadas.parquet")
        coords["location_id"] = coords["location_id"].astype(str)
        if coords["location_id"].duplicated().any():
            raise ValueError("coordenadas.parquet tem IDs repetidos.")
        self.coordinates = coords[["location_id", "latitude", "longitude"]]
        static = pd.read_parquet(run / "estaticas.parquet")
        static["location_id"] = static["location_id"].astype(str)
        self.static = static
        clusters_path = run / "clusters.parquet"
        self.clusters: dict[str, int] = {}
        self.anomes_cluster: int | None = None
        if clusters_path.is_file():
            clusters = pd.read_parquet(clusters_path).dropna(subset=["cluster"])
            self.anomes_cluster = int(clusters["anomes"].max())
            latest = clusters[clusters["anomes"] == self.anomes_cluster]
            self.clusters = dict(zip(latest["location_id"].astype(str),
                                     latest["cluster"].astype(int), strict=True))
        terra = settings.recomendacoes_terra_path
        self.terra_path = terra
        self.terra_columns = pq.ParquetFile(terra).schema_arrow.names
        months = pd.read_parquet(terra, columns=["anomes"])["anomes"].unique()
        self.observed = sorted(period(m) for m in months)
        self.history_sha = file_sha256(terra)
        self.bundle: ProjectionBundle = load_bundle(settings.recomendacoes_modelo_path)
        if self.bundle.cutoff != self.observed[-1]:
            raise ValueError(
                f"Pacote com origem {self.bundle.cutoff} e histórico até {self.observed[-1]}: "
                "a publicação está inconsistente.")
        self.dynamic = [c for c in self.terra_columns if c not in KEY]
        self.variables = [v for v in self.bundle.variables if v in self.dynamic]
        self.trajectory = trajectory_key(self.bundle.sha256, self.history_sha, self.variables)

    def body_niches(self, body: str) -> list[str]:
        return [TODOS, *self.niches[body]]

    def bases(self) -> list[tuple[str, str]]:
        return [(str(base_id), body) for body in BODIES
                for base_id in self.references[body]["base_id"]]

    def publication(self) -> Publicacao:
        return Publicacao(
            corte=to_anomes(self.bundle.cutoff),
            horizontes_diretos={v: self.bundle.horizons(v) for v in self.variables},
            estrategias=["recursiva", "auto", "sazonal"],
            algoritmo=f"{ALGORITHM_VERSION}/esquema-{SCHEMA_VERSION}",
            modelo_sha256=self.bundle.sha256,
            historico_sha256=self.history_sha,
            trajetoria=self.trajectory,
        )

    def read_months(self, months: list[pd.Period], columns: list[str]) -> pd.DataFrame:
        frame = pd.read_parquet(
            self.terra_path, columns=[*KEY, *columns],
            filters=[("anomes", "in", [to_anomes(m) for m in months])])
        frame["location_id"] = frame["location_id"].astype(str)
        return frame


class RecommendationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._publication: Publication | None = None
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=settings.recomendacoes_workers,
                                            thread_name_prefix="projecao")
        self._snapshots: LRU[tuple[str, int], Snapshot] = LRU(4)
        self._rankings: LRU[tuple[Any, ...], pd.DataFrame] = LRU(64)
        self.timings: dict[str, float] = {}

    # ------------------------------------------------------------- publication
    @property
    def publication(self) -> Publication:
        with self._lock:
            if self._publication is None:
                try:
                    self._publication = Publication(self.settings)
                except (OSError, ValueError, KeyError) as exc:
                    logger.exception("publicacao_invalida")
                    raise ApiError(503, "publicacao_indisponivel",
                                   f"Publicação de recomendações indisponível: {exc}") from exc
            return self._publication

    def store(self) -> TrajectoryStore:
        pub = self.publication
        return TrajectoryStore(self.settings.recomendacoes_cache_dir, pub.trajectory, {
            "corte": to_anomes(pub.bundle.cutoff), "modelo_sha256": pub.bundle.sha256,
            "historico_sha256": pub.history_sha, "algoritmo": ALGORITHM_VERSION,
            "esquema": SCHEMA_VERSION, "variaveis": pub.variables,
            "modelo": str(self.settings.recomendacoes_modelo_path),
            "historico": str(pub.terra_path),
        })

    def options(self) -> OpcoesResponse:
        pub = self.publication
        bases = []
        for base_id, body in pub.bases():
            geometry = pub.base_geometry.get(base_id, {})
            bases.append(BaseOpcao(
                base_id=base_id, corpo=body,  # type: ignore[arg-type]
                nome=str(geometry.get("nome", base_id)),
                latitude=geometry.get("latitude"), longitude=geometry.get("longitude"),
                raio_km=geometry.get("raio_km"), nichos=pub.body_niches(body)))
        return OpcoesResponse(
            bases=bases, meses_observados=[to_anomes(m) for m in pub.observed],
            anomes_max=self.settings.recomendacoes_anomes_max,
            k_max=self.settings.recomendacoes_k_max, cobertura_minima_padrao=MIN_COVERAGE,
            publicacao=pub.publication())

    # -------------------------------------------------------------- projection
    def _load_observed_window(self) -> dict[pd.Period, pd.DataFrame]:
        pub = self.publication
        cutoff = pub.bundle.cutoff
        months = [cutoff - offset for offset in range(WINDOW_MONTHS)]
        history = pub.read_months(months, pub.variables)
        ids = pd.Index(pub.coordinates["location_id"], name="location_id")
        return observed_window(history, cutoff, ids, pub.variables)

    def _run(self, job: Job) -> None:
        job.status = "rodando"
        started = time.perf_counter()
        pub = self.publication

        def progress(month: pd.Period, done: int, total: int, _: bool) -> None:
            job.done, job.total = done, total

        try:
            project_until(job.target, pub.bundle, self.store(), self._load_observed_window,
                          pub.variables, progress=progress, should_extend=lambda: job.target,
                          batch_size=self.settings.recomendacoes_lote_ids)
            job.status = "pronto"
            logger.info("projecao_concluida", extra={
                "tarefa": job.id, "destino": to_anomes(job.target), "meses": job.done,
                "segundos": round(time.perf_counter() - started, 2)})
        except Exception as exc:
            job.status, job.error = "falhou", f"{type(exc).__name__}: {exc}"
            logger.exception("projecao_falhou", extra={"tarefa": job.id})
        finally:
            job.finished = time.monotonic()

    def ensure_projection(self, target: pd.Period) -> Calculando | None:
        """None when ``target`` is materialized; otherwise the job state (202 body)."""
        pub = self.publication
        cutoff = pub.bundle.cutoff
        store = self.store()
        done = store.last_contiguous(cutoff)
        needed = (target - cutoff).n
        if done >= target:
            return None
        with self._lock:
            job = self._jobs.get(pub.trajectory)
            if job is not None and job.status in ("fila", "rodando"):
                job.target = max(job.target, target)
            elif (job is not None and job.status == "falhou" and job.finished is not None
                  and time.monotonic() - job.finished < FAILURE_TTL_SECONDS):
                raise ApiError(500, "projecao_falhou",
                               "A projeção falhou; tente de novo em instantes.",
                               {"tarefa_id": job.id, "erro": job.error,
                                "repetir_em_segundos": int(FAILURE_TTL_SECONDS)})
            else:
                running = sum(j.status in ("fila", "rodando") for j in self._jobs.values())
                if running >= self.settings.recomendacoes_fila_max:
                    raise ApiError(503, "fila_cheia", "Fila de projeções cheia.",
                                   {"repetir_em_segundos":
                                    self.settings.recomendacoes_retry_segundos})
                job = Job(id=uuid.uuid4().hex[:12], target=target,
                          done=(done - cutoff).n, total=needed)
                self._jobs[pub.trajectory] = job
                self._executor.submit(self._run, job)
        return Calculando(
            anomes=to_anomes(target), estrategia="recursiva",
            repetir_em_segundos=self.settings.recomendacoes_retry_segundos,
            tarefa_id=job.id, meses_calculados=max(job.done, (done - cutoff).n),
            meses_necessarios=needed, na_fila=job.status == "fila")

    # ---------------------------------------------------------------- snapshot
    def snapshot(self, month: pd.Period, strategy: str) -> Snapshot | Calculando:
        pub = self.publication
        cutoff = pub.bundle.cutoff
        if month < pub.observed[0]:
            raise ApiError(404, "anterior_ao_historico",
                           f"O histórico começa em {to_anomes(pub.observed[0])}.",
                           {"anomes": to_anomes(month)})
        origin = origin_for(month, cutoff, pub.bundle.max_horizon, strategy,
                            set(pub.observed))
        horizon = max(0, (month - cutoff).n)
        if origin == "observada":
            if month not in set(pub.observed):
                raise ApiError(404, "mes_sem_observacao",
                               f"{to_anomes(month)} não tem observações no histórico.",
                               {"anomes": to_anomes(month)})
            key = ("observada", to_anomes(month))
            return self._snapshots.get(key, lambda: Snapshot(
                self._with_static(pub.read_months([month], pub.variables)), origin, strategy,
                0, None, dict.fromkeys(pub.variables, "observado"), key))
        if origin == "cenario_sazonal":
            base = seasonal_base(month, cutoff)
            key = ("sazonal", to_anomes(base))
            observed = self._snapshots.get(("observada", to_anomes(base)), lambda: Snapshot(
                self._with_static(pub.read_months([base], pub.variables)), "observada",
                strategy, 0, None, {}, ("observada", to_anomes(base))))
            return Snapshot(observed.frame, origin, strategy, horizon, to_anomes(base),
                            {v: f"observado_{to_anomes(base)}" for v in pub.variables}, key)
        pending = self.ensure_projection(month)
        if pending is not None:
            return pending
        store = self.store()
        key = (pub.trajectory, to_anomes(month))
        effective = "recursiva" if strategy in ("recursiva", "auto") else strategy

        def load() -> Snapshot:
            frame = store.read(month).reset_index()
            frame["location_id"] = frame["location_id"].astype(str)
            methods = store.months_index().get(str(to_anomes(month)), {}).get("metodos", {})
            return Snapshot(self._with_static(frame), origin, effective, horizon, None,
                            methods, key)

        return self._snapshots.get(key, load)

    def _with_static(self, dynamic: pd.DataFrame) -> pd.DataFrame:
        pub = self.publication
        frame = dynamic.drop(columns=["anomes"], errors="ignore")
        frame["location_id"] = frame["location_id"].astype(str)
        if frame["location_id"].duplicated().any():
            raise ApiError(500, "chave_duplicada", "Estado terrestre com IDs repetidos.")
        return pub.static.merge(frame, on="location_id", how="left", validate="one_to_one")

    # ----------------------------------------------------------------- ranking
    def _criteria(self, body: str, base_id: str, niche: str) -> dict[str, tuple[float, float,
                                                                                float]]:
        pub = self.publication
        return profile_criteria(pub.niches_path, body, niche, pub.references[body], base_id)

    def _ranking(self, snap: Snapshot, body: str, base_id: str, niche: str,
                 coverage: float) -> pd.DataFrame:
        def build() -> pd.DataFrame:
            criteria = self._criteria(body, base_id, niche)
            columns = [c for c in criteria if c in snap.frame.columns]
            values = snap.frame[["location_id", *columns]].copy()
            for missing in set(criteria) - set(columns):
                values[missing] = float("nan")
            return recommend(values, self.publication.coordinates, criteria,
                             min_coverage=coverage)

        return self._rankings.get((snap.key, base_id, niche, coverage), build)

    def recommend(
        self, *, anomes: int, niche: str, base_id: str | None, body: str | None, k: int,
        offset: int, coverage: float, strategy: str,
    ) -> RecomendacoesResponse | Calculando:
        started = time.perf_counter()
        pub = self.publication
        try:
            month = period(anomes)
        except ValueError as exc:
            raise ApiError(400, "anomes_invalido", str(exc), {"anomes": anomes}) from exc
        if anomes > self.settings.recomendacoes_anomes_max:
            raise ApiError(400, "anomes_fora_do_calendario",
                           f"Calendário suportado até {self.settings.recomendacoes_anomes_max}.",
                           {"anomes": anomes})
        bases = pub.bases()
        if base_id is not None:
            match = [b for b in bases if b[0] == base_id]
            if not match:
                raise ApiError(404, "base_not_found", f"A base '{base_id}' não existe.",
                               {"base_id": base_id})
            if body is not None and match[0][1] != body:
                raise ApiError(400, "base_corpo_incoerente",
                               f"A base '{base_id}' é de {match[0][1]}, não de {body}.",
                               {"base_id": base_id, "corpo": body})
            bases = match
        elif body is not None:
            bases = [b for b in bases if b[1] == body]
        known = {n for b in BODIES for n in pub.body_niches(b)}
        if niche not in known:
            raise ApiError(400, "nicho_invalido", f"Nicho '{niche}' não existe.",
                           {"nicho": niche, "permitidos": sorted(known)})
        snap = self.snapshot(month, strategy)
        if isinstance(snap, Calculando):
            return snap
        self.timings["estado"] = time.perf_counter() - started
        groups = [self._group(snap, base, body_, niche, coverage, k, offset)
                  for base, body_ in bases]
        self.timings["ranking"] = time.perf_counter() - started
        exploratory = snap.origem in ("extrapolada", "cenario_sazonal")
        return RecomendacoesResponse(
            anomes=anomes, nicho=niche, origem=snap.origem,  # type: ignore[arg-type]
            estrategia=snap.estrategia,  # type: ignore[arg-type]
            horizonte_meses=snap.horizonte, mes_base_cenario=snap.mes_base,
            anomes_cluster=pub.anomes_cluster,
            rotulo="Projeção exploratória" if exploratory else None,
            metodos=snap.metodos, cobertura_minima=coverage, k=k, offset=offset,
            publicacao=pub.publication(), resultados=groups)

    def _group(self, snap: Snapshot, base_id: str, body: str, niche: str, coverage: float,
               k: int, offset: int) -> GrupoBase:
        pub = self.publication
        geometry = pub.base_geometry.get(base_id, {})
        common = {"base_id": base_id, "corpo": body, "nome": str(geometry.get("nome", base_id)),
                  "latitude": geometry.get("latitude"), "longitude": geometry.get("longitude")}
        if niche != TODOS and niche not in pub.niches[body]:
            return GrupoBase(**common, status="nicho_incompativel", criterios=[],
                             total_elegiveis=0, candidatos=[])
        criteria = self._criteria(body, base_id, niche)
        frame = snap.frame
        missing = [v for v in criteria
                   if v not in frame.columns or frame[v].notna().sum() == 0]
        ranked = self._ranking(snap, body, base_id, niche, coverage)
        page = ranked.iloc[offset: offset + k]
        candidates = []
        for position, row in enumerate(page.to_dict("records"), start=offset + 1):
            values = {v: _number(row.get(v)) for v in criteria}
            candidates.append(Candidato(
                posicao=position, location_id=str(row["location_id"]),
                latitude=float(row["latitude"]), longitude=float(row["longitude"]),
                nota=float(row["nota"]), cobertura=float(row["cobertura"]),
                cluster=pub.clusters.get(str(row["location_id"])), valores=values,
                notas_criterios={v: _number(row.get(f"nota_{v}")) for v in criteria},
                criterios_sem_dado=[v for v, value in values.items() if value is None]))
        if ranked.empty:
            status = "sem_dados" if missing else "sem_candidatos"
        else:
            status = "parcial" if missing else "ok"
        info = {key[1]: value for key, value in pub.target_info.items() if key[0] == base_id}
        return GrupoBase(
            **common, status=status,  # type: ignore[arg-type]
            criterios=[Criterio(
                variavel=v, nome=variable_label(v)[0], unidade=variable_label(v)[1],
                alvo=t, tolerancia=tol, peso=w, tipo_alvo=info.get(v, {}).get("tipo_alvo"),
                fonte=info.get(v, {}).get("fonte")) for v, (t, tol, w) in criteria.items()],
            criterios_ausentes=missing, total_elegiveis=len(ranked), candidatos=candidates)

    def job_states(self) -> list[dict[str, Any]]:
        return [{"tarefa_id": j.id, "destino": to_anomes(j.target), "status": j.status,
                 "meses_calculados": j.done, "meses_necessarios": j.total, "erro": j.error}
                for j in self._jobs.values()]

    def wait(self, timeout: float = 600.0) -> None:
        """Block until queued jobs finish (scripts and tests)."""
        deadline = time.monotonic() + timeout
        while any(j.status in ("fila", "rodando") for j in self._jobs.values()):
            if time.monotonic() > deadline:
                raise TimeoutError("Projeção não terminou no tempo de espera.")
            time.sleep(0.05)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_service(settings: Settings) -> RecommendationService:
    return RecommendationService(settings)


def anomes_path(root: Path, anomes: int) -> Path:
    return root / f"{anomes}.parquet"
