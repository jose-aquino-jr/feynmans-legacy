"""Pares de análogos Terra ↔ Lua/Marte publicados para a API e o mapa 3D.

Cada base de referência (Lua ou Marte) é comparada a todas as células terrestres
com o ranking de ``analog_study.recommend``, uma vez com o perfil completo
(``Todos``) e uma vez por nicho. Os pares escolhidos combinam:

* ``geral``: melhores notas no perfil completo, espalhadas pelo globo;
* ``especialista``: muito parecidos em um nicho (térmico, geologia...), mesmo
  que a nota geral seja baixa;
* ``destaque``: locais curados em ``config/locais_destaque.json`` comparados com
  todas as bases.

Locais dentro dos raios de ``config/analogos_classicos.json`` ficam fora da
seleção automática, para que o software proponha lugares novos.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analog_study import KEY, MIN_COVERAGE, profile_criteria, recommend

EARTH_RADIUS_KM = 6371.0
NICHE_MIN_COVERAGE = 0.5
CLIMATE_MONTHS = 12
SITE_RADIUS_KM = 150.0
STRONG_SCORE = 75.0
WEAK_SCORE = 50.0
BODIES = ("lua", "marte")
PAIR_TYPES = ("destaque", "geral", "especialista")


@dataclass(frozen=True)
class Zone:
    nome: str
    latitude: float
    longitude: float
    raio_km: float


@dataclass(frozen=True)
class SelectionConfig:
    n_geral: int = 8
    n_por_nicho: int = 2
    min_nota_nicho: float = 80.0
    separacao_km: float = 500.0


@dataclass
class AnalogInputs:
    """Dados já carregados, para que a seleção possa ser testada sem arquivos."""

    earth: pd.DataFrame
    coordinates: pd.DataFrame
    niches_path: Path
    references: Mapping[str, pd.DataFrame]
    bases: Mapping[str, Mapping[str, Any]]
    classics: Sequence[Zone] = ()
    featured: Sequence[Mapping[str, Any]] = ()
    names: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


def haversine_km(
    latitude: np.ndarray | pd.Series, longitude: np.ndarray | pd.Series,
    lat0: float, lon0: float,
) -> np.ndarray:
    """Great-circle distance in km from many points to one point."""
    lat1 = np.radians(np.asarray(latitude, dtype=float))
    lon1 = np.radians(np.asarray(longitude, dtype=float))
    lat2, lon2 = np.radians(lat0), np.radians(lon0)
    half = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return np.asarray(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(half, 0, 1))))


def outside_zones(frame: pd.DataFrame, zones: Iterable[Zone]) -> pd.Series:
    """True for rows farther than every zone radius."""
    keep = pd.Series(True, index=frame.index)
    for zone in zones:
        distance = haversine_km(frame["latitude"], frame["longitude"],
                                zone.latitude, zone.longitude)
        keep &= distance > zone.raio_km
    return keep


def pick_spread(ranked: pd.DataFrame, k: int, min_km: float) -> pd.DataFrame:
    """Take rows in order, skipping any closer than ``min_km`` to a chosen one."""
    chosen: list[Any] = []
    lats: list[float] = []
    lons: list[float] = []
    for row in ranked[["latitude", "longitude"]].itertuples():
        if len(chosen) >= k:
            break
        if lats and haversine_km(np.array(lats), np.array(lons),
                                 row.latitude, row.longitude).min() < min_km:
            continue
        chosen.append(row.Index)
        lats.append(row.latitude)
        lons.append(row.longitude)
    return ranked.loc[chosen]


def niche_names(niches_path: Path, body: str) -> list[str]:
    config: dict[str, dict[str, Any]] = json.loads(niches_path.read_text(encoding="utf-8"))
    return list(config[body])


def base_scores(inputs: AnalogInputs, body: str, base_id: str) -> pd.DataFrame:
    """Overall and per-niche scores of every Earth cell for one base."""
    reference = inputs.references[body]
    criteria = profile_criteria(inputs.niches_path, body, "Todos", reference, base_id)
    overall = recommend(inputs.earth[["location_id", *criteria]], inputs.coordinates,
                        criteria, min_coverage=NICHE_MIN_COVERAGE)
    scores = overall.set_index("location_id")[["latitude", "longitude", "nota", "cobertura"]]
    scores = scores.rename(columns={"nota": "nota_geral"})
    scores.loc[scores["cobertura"] < MIN_COVERAGE - 1e-9, "nota_geral"] = np.nan
    for niche in niche_names(inputs.niches_path, body):
        niche_criteria = profile_criteria(inputs.niches_path, body, niche, reference, base_id)
        ranked = recommend(inputs.earth[["location_id", *niche_criteria]],
                           inputs.coordinates, niche_criteria,
                           min_coverage=NICHE_MIN_COVERAGE).set_index("location_id")
        scores[f"nota_{niche}"] = ranked["nota"]
        scores[f"cobertura_{niche}"] = ranked["cobertura"]
    return scores


def strengths(row: pd.Series, niches: Sequence[str]) -> tuple[str, str]:
    """Comma-separated strongest and weakest niches of one pair."""
    values = {niche: row.get(f"nota_{niche}") for niche in niches}
    known = {name: float(value) for name, value in values.items() if pd.notna(value)}
    strong = sorted((n for n, v in known.items() if v >= STRONG_SCORE),
                    key=lambda n: -known[n])[:3]
    weak = sorted((n for n, v in known.items() if v < WEAK_SCORE),
                  key=lambda n: known[n])[:3]
    return ",".join(strong), ",".join(weak)


def select_locations(
    scores: pd.DataFrame, niches: Sequence[str], zones: Sequence[Zone],
    config: SelectionConfig,
) -> dict[str, tuple[str, list[str]]]:
    """Choose ``location_id -> (tipo, nichos_destaque)`` for one base."""
    allowed = scores[outside_zones(scores, zones)]
    general = allowed.dropna(subset=["nota_geral"]).sort_values(
        ["nota_geral"], ascending=False, kind="stable")
    picks: dict[str, tuple[str, list[str]]] = {
        str(location): ("geral", [])
        for location in pick_spread(general, config.n_geral, config.separacao_km).index
    }
    for niche in niches:
        column = f"nota_{niche}"
        candidates = allowed[allowed[column] >= config.min_nota_nicho].sort_values(
            [column, "nota_geral"], ascending=False, na_position="last", kind="stable")
        for location in pick_spread(candidates, config.n_por_nicho, config.separacao_km).index:
            kind, labels = picks.get(str(location), ("especialista", []))
            picks[str(location)] = (kind, [*labels, niche])
    return picks


WATER_COLUMN = "biologia__cobertura_agua_fracao"
MAX_WATER_FRACTION = 0.5


def land_locations(values: pd.DataFrame) -> set[str]:
    """Cells mostly covered by water (lakes, coast) are not proposed as analogs."""
    if WATER_COLUMN not in values.columns:
        return set(values["location_id"].astype(str))
    water = values[WATER_COLUMN].fillna(0)
    return set(values.loc[water <= MAX_WATER_FRACTION, "location_id"].astype(str))


def nearest_location(coordinates: pd.DataFrame, latitude: float, longitude: float) -> str:
    distance = haversine_km(coordinates["latitude"], coordinates["longitude"],
                            latitude, longitude)
    return str(coordinates["location_id"].iloc[int(np.argmin(distance))])


def coordinate_label(latitude: float, longitude: float) -> str:
    lat = f"{abs(latitude):.2f}°{'N' if latitude >= 0 else 'S'}"
    lon = f"{abs(longitude):.2f}°{'L' if longitude >= 0 else 'O'}"
    return f"{lat}, {lon}"


def name_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.2f},{longitude:.2f}"


def build_pairs(
    inputs: AnalogInputs, config: SelectionConfig = SelectionConfig(),
) -> dict[str, pd.DataFrame]:
    """Build the bases, Earth sites, pairs and per-niche scores tables."""
    featured_ids: dict[str, Mapping[str, Any]] = {
        nearest_location(inputs.coordinates, float(item["latitude"]),
                         float(item["longitude"])): item
        for item in inputs.featured
    }
    land = land_locations(inputs.earth)
    pair_rows: list[dict[str, Any]] = []
    niche_rows: list[dict[str, Any]] = []
    base_rows: list[dict[str, Any]] = []
    for body in BODIES:
        niches = niche_names(inputs.niches_path, body)
        for base_id in inputs.references[body]["base_id"]:
            base = inputs.bases[str(base_id)]
            scores = base_scores(inputs, body, str(base_id))
            picks = select_locations(scores[scores.index.isin(land)], niches,
                                     inputs.classics, config)
            for location in featured_ids:
                _, labels = picks.get(location, ("destaque", []))
                picks[location] = ("destaque", labels)
            chosen = scores.loc[[loc for loc in picks if loc in scores.index]]
            chosen = chosen.sort_values("nota_geral", ascending=False, na_position="last")
            for rank, (location, row) in enumerate(chosen.iterrows(), start=1):
                kind, labels = picks[str(location)]
                strong, weak = strengths(row, niches)
                pair_id = f"{base_id}__{location}"
                pair_rows.append({
                    "par_id": pair_id, "corpo": body, "base_id": str(base_id),
                    "location_id": str(location), "tipo": kind,
                    "destaque": str(location) in featured_ids,
                    "nichos_destaque": ",".join(labels), "rank_base": rank,
                    "nota_geral": row["nota_geral"], "cobertura": row["cobertura"],
                    "pontos_fortes": strong, "pontos_fracos": weak,
                })
                niche_rows.extend({
                    "par_id": pair_id, "corpo": body, "base_id": str(base_id),
                    "location_id": str(location), "nicho": niche,
                    "nota": row[f"nota_{niche}"], "cobertura": row[f"cobertura_{niche}"],
                } for niche in niches)
            best = chosen.dropna(subset=["nota_geral"])
            base_rows.append({
                "base_id": str(base_id), "corpo": body, "nome": base["nome"],
                "descricao": str(inputs.references[body].set_index("base_id").loc[
                    base_id, "descricao"]),
                "latitude": float(base["latitude"]), "longitude": float(base["longitude"]),
                "raio_km": float(base["raio_km"]), "n_pares": len(chosen),
                "melhor_location_id": str(best.index[0]) if not best.empty else None,
                "melhor_nota": float(best["nota_geral"].iloc[0]) if not best.empty else None,
            })
    pairs = pd.DataFrame(pair_rows)
    sites = build_sites(inputs, pairs, featured_ids)
    return {
        "bases": pd.DataFrame(base_rows),
        "locais": sites,
        "pares": pairs,
        "pares_nichos": pd.DataFrame(niche_rows),
    }


def build_sites(
    inputs: AnalogInputs, pairs: pd.DataFrame,
    featured_ids: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    """One row per Earth site present in any pair."""
    ids = pairs["location_id"].drop_duplicates()
    sites = inputs.coordinates.set_index("location_id").loc[ids].reset_index()
    sites = sites.merge(inputs.earth.rename(columns={
        "temperatura__ar_2m_c": "temperatura_media_c",
        "agua_gelo__precipitacao_mm_dia": "precipitacao_mm_dia",
        "relevo__elevacao_media_m": "elevacao_media_m",
        "biologia__ndvi": "ndvi",
    })[["location_id", "temperatura_media_c", "precipitacao_mm_dia",
        "elevacao_media_m", "ndvi"]], on="location_id", how="left", validate="one_to_one")
    names, regions, countries, descriptions = [], [], [], []
    for site in sites.itertuples():
        found = inputs.names.get(name_key(site.latitude, site.longitude), {})
        curated = featured_ids.get(str(site.location_id), {})
        region = found.get("regiao")
        country = found.get("pais") or ("Antártida" if site.latitude < -60 else None)
        coordinates = coordinate_label(site.latitude, site.longitude)
        if curated.get("nome"):
            label = str(curated["nome"])
        elif region and country:
            label = f"{region}, {country}"
        elif country:
            label = f"{country} — {coordinates}"
        else:
            label = coordinates
        names.append(label)
        regions.append(region)
        countries.append(country)
        descriptions.append(curated.get("descricao"))
    sites["nome"] = names
    sites["regiao"] = regions
    sites["pais"] = countries
    sites["descricao"] = descriptions
    sites["destaque"] = sites["location_id"].isin(list(featured_ids))
    sites["raio_km"] = SITE_RADIUS_KM
    counts = pairs.groupby("location_id").agg(
        n_pares=("par_id", "size"), melhor_nota=("nota_geral", "max"))
    sites = sites.merge(counts, left_on="location_id", right_index=True, how="left")
    columns = ["location_id", "nome", "regiao", "pais", "descricao", "destaque",
               "latitude", "longitude", "raio_km", "n_pares", "melhor_nota",
               "temperatura_media_c", "precipitacao_mm_dia", "elevacao_media_m", "ndvi"]
    return sites[columns].sort_values(["destaque", "melhor_nota"], ascending=False,
                                      na_position="last", ignore_index=True)


def score_series(
    monthly: pd.DataFrame, static: pd.DataFrame, inputs: AnalogInputs,
    pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Overall score of each pair per month (``monthly`` has KEY, ``origem`` and values)."""
    rows: list[pd.DataFrame] = []
    locations = pairs["location_id"].unique()
    frame = monthly[monthly["location_id"].isin(locations)].merge(
        static, on="location_id", how="left", validate="many_to_one")
    for (month, origin), values in frame.groupby(["anomes", "origem"], sort=True):
        for body in BODIES:
            reference = inputs.references[body]
            for base_id in reference["base_id"]:
                criteria = profile_criteria(inputs.niches_path, body, "Todos",
                                            reference, str(base_id))
                ranked = recommend(values[["location_id", *criteria]],
                                   inputs.coordinates, criteria)
                ranked = ranked[["location_id", "nota", "cobertura"]].assign(
                    base_id=str(base_id), anomes=int(month), origem=str(origin))
                rows.append(ranked)
    scored = pd.concat(rows, ignore_index=True)
    series = pairs[["par_id", "base_id", "location_id"]].merge(
        scored, on=["base_id", "location_id"], how="inner")
    return series[["par_id", "anomes", "origem", "nota", "cobertura"]].sort_values(
        ["par_id", "anomes"], ignore_index=True)


def load_inputs(root: Path, months: int = CLIMATE_MONTHS) -> tuple[AnalogInputs, list[int]]:
    """Read the project files; dynamic variables are averaged over the last months."""
    run = root / "data/terra/analise_analogos"
    selection = json.loads((run / "selecao.json").read_text(encoding="utf-8"))
    observed = sorted(int(month) for month in selection["anomes_observados"])[-months:]
    niches_path = root / "config/nichos.json"
    config: dict[str, dict[str, list[dict[str, Any]]]] = json.loads(
        niches_path.read_text(encoding="utf-8"))
    static = pd.read_parquet(run / "estaticas.parquet")
    wanted = {item["terra"] for body in config.values() for niche in body.values()
              for item in niche}
    wanted |= {"temperatura__ar_2m_c", "agua_gelo__precipitacao_mm_dia", "biologia__ndvi"}
    dynamic = sorted(wanted - set(static.columns))
    history = pd.read_parquet(root / "data/terra/terra.parquet",
                              columns=[*KEY, *dynamic], filters=[("anomes", "in", observed)])
    climate = history.groupby("location_id", as_index=False)[dynamic].mean()
    values = static.merge(climate, on="location_id", how="left", validate="one_to_one")
    bases_config = json.loads((root / "config/bases_espaciais.json").read_text(encoding="utf-8"))
    classics = json.loads((root / "config/analogos_classicos.json").read_text(encoding="utf-8"))
    featured_path = root / "config/locais_destaque.json"
    featured = (json.loads(featured_path.read_text(encoding="utf-8"))["locais"]
                if featured_path.is_file() else [])
    names_path = root / "config/nomes_locais.json"
    names = (json.loads(names_path.read_text(encoding="utf-8"))["locais"]
             if names_path.is_file() else {})
    inputs = AnalogInputs(
        earth=values,
        coordinates=pd.read_parquet(run / "coordenadas.parquet"),
        niches_path=niches_path,
        references={body: pd.read_parquet(root / "data" / body / f"{body}.parquet")
                    for body in BODIES},
        bases={key: value for key, value in bases_config.items() if not key.startswith("_")},
        classics=[Zone(**zone) for zone in classics["locais"]],
        featured=featured,
        names=names,
    )
    return inputs, observed


SIDECARS: dict[str, dict[str, Any]] = {
    "bases": {
        "description": "Bases de referência na Lua e em Marte com o ponto para o mapa 3D.",
        "id_column": "base_id",
        "tags": ["análogos", "lua", "marte"],
        "columns": {
            "latitude": "Latitude planetocêntrica aproximada do sítio (graus).",
            "longitude": "Longitude leste aproximada do sítio, em [-180, 180].",
            "raio_km": "Raio sugerido para o destaque no globo.",
            "n_pares": "Quantidade de locais terrestres relacionados.",
            "melhor_nota": "Maior nota geral entre os pares (0 a 100).",
        },
    },
    "locais": {
        "description": "Locais terrestres relacionados a alguma base da Lua ou de Marte.",
        "id_column": "location_id",
        "tags": ["análogos", "terra"],
        "columns": {
            "destaque": "Local curado em config/locais_destaque.json (padrão do software).",
            "raio_km": "Raio sugerido para o destaque no globo.",
            "melhor_nota": "Maior nota geral entre as bases relacionadas.",
            "temperatura_media_c": "Média dos últimos meses observados.",
            "precipitacao_mm_dia": "Média dos últimos meses observados.",
        },
    },
    "pares": {
        "description": "Relação base espacial ↔ local terrestre com notas e pontos fortes/fracos.",
        "id_column": "par_id",
        "tags": ["análogos"],
        "columns": {
            "tipo": "destaque (curado), geral (melhor nota geral) ou especialista (um nicho).",
            "nichos_destaque": "Nichos que motivaram a escolha, separados por vírgula.",
            "rank_base": "Posição do local entre os pares da mesma base (1 = melhor).",
            "nota_geral": "Nota 0–100 no perfil completo; nula se cobertura < 0,7.",
            "cobertura": "Fração do peso do perfil com dados no local.",
            "pontos_fortes": "Até 3 nichos com nota >= 75, separados por vírgula.",
            "pontos_fracos": "Até 3 nichos com nota < 50, separados por vírgula.",
        },
    },
    "pares_nichos": {
        "description": "Nota de cada par em cada nicho (térmico, geologia, terreno...).",
        "tags": ["análogos"],
        "columns": {"nota": "Nota 0–100 no nicho; nula sem dados suficientes."},
    },
    "series": {
        "description": "Nota geral mensal de cada par: meses observados e previstos pelo LightGBM.",
        "tags": ["análogos", "previsão"],
        "columns": {"origem": "observada ou prevista."},
    },
}


def generate(root: Path, out_dir: Path,
             config: SelectionConfig = SelectionConfig()) -> dict[str, pd.DataFrame]:
    """Build every analog table and write it as Parquet plus sidecar metadata."""
    inputs, observed = load_inputs(root)
    tables = build_pairs(inputs, config)
    static = pd.read_parquet(root / "data/terra/analise_analogos/estaticas.parquet")
    dynamic = [column for column in inputs.earth.columns
               if column not in static.columns]
    monthly = monthly_values(root, observed, tables["pares"]["location_id"].unique(), dynamic)
    tables["series"] = score_series(monthly, static, inputs, tables["pares"])
    out_dir.mkdir(parents=True, exist_ok=True)
    period = f"{observed[0]}–{observed[-1]}"
    for name, frame in tables.items():
        frame.to_parquet(out_dir / f"{name}.parquet", index=False)
        sidecar = {**SIDECARS[name], "source": "src/feynmans_legacy/analog_pairs.py",
                   "metadata": {"meses_climatologia": period}}
        (out_dir / f"{name}.meta.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return tables


def monthly_values(root: Path, observed: Sequence[int], locations: Iterable[str],
                   variables: Sequence[str]) -> pd.DataFrame:
    """Observed months plus the published forecasts, in long ``KEY + origem`` form."""
    ids = list(locations)
    run = root / "data/terra/analise_analogos"
    seen = pd.read_parquet(root / "data/terra/terra.parquet", columns=[*KEY, *variables],
                           filters=[("anomes", "in", list(observed)),
                                    ("location_id", "in", ids)])
    forecast = pd.read_parquet(run / "previsoes.parquet",
                               filters=[("location_id", "in", ids)])
    future = forecast.pivot_table(index=KEY, columns="variavel",  # noqa: PD010
                                  values="valor_previsto").reset_index()
    return pd.concat([seen.assign(origem="observada"), future.assign(origem="prevista")],
                     ignore_index=True)
