"""Pré-calcula a projeção recursiva e grava o manifesto da publicação.

Uso (na raiz do projeto):

    python scripts/publicar_projecoes.py                 # 12 meses após o corte
    python scripts/publicar_projecoes.py --ate 204007    # até julho de 2040
    python scripts/publicar_projecoes.py --verificar     # só confere a publicação

Escreve ``data/terra/analise_analogos/manifesto_publicacao.json`` com corte,
hashes do modelo e do histórico, versões, features, horizontes, contagens derivadas
dos próprios arquivos e a trajetória em ``cache_projecoes/``. Retoma do último mês
gravado; pode ser interrompido e rodado de novo.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from app.config import Settings  # noqa: E402
from app.services.recommendations import RecommendationService  # noqa: E402

from feynmans_legacy.analog_study import FEATURES, LAGS  # noqa: E402
from feynmans_legacy.forecast_projection import (  # noqa: E402
    ALGORITHM_VERSION,
    SCHEMA_VERSION,
    period,
    to_anomes,
)

PACKAGES = ("python", "lightgbm", "numpy", "pandas", "scikit-learn", "pyarrow", "fastapi")


def versions() -> dict[str, str]:
    found = {"python": platform.python_version()}
    for name in PACKAGES[1:]:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = "ausente"
    return found


def manifest(service: RecommendationService, measured: dict[str, object]) -> dict[str, object]:
    import pandas as pd

    pub = service.publication
    keys = pd.read_parquet(pub.terra_path, columns=["location_id", "anomes"])
    store = service.store()
    done = store.last_contiguous(pub.bundle.cutoff)
    return {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "corte": to_anomes(pub.bundle.cutoff),
        "historico": {
            "arquivo": pub.terra_path.relative_to(ROOT).as_posix(), "sha256": pub.history_sha,
            "linhas": int(len(keys)), "locais": int(keys["location_id"].nunique()),
            "meses": int(keys["anomes"].nunique()), "primeiro_mes": int(keys["anomes"].min()),
            "ultimo_mes": int(keys["anomes"].max()),
            "chaves_duplicadas": int(keys.duplicated().sum()),
            "variaveis_dinamicas": pub.dynamic,
        },
        "modelo": {
            "arquivo": service.settings.recomendacoes_modelo_path.relative_to(ROOT).as_posix(),
            "sha256": pub.bundle.sha256, "features": FEATURES, "lags": LAGS,
            "horizontes": {v: pub.bundle.horizons(v) for v in pub.bundle.variables},
            "persistencia_explicita": [f"{v}/H{h}" for (v, h), m in pub.bundle.models.items()
                                       if m is None],
        },
        "coordenadas": {"locais": int(len(pub.coordinates))},
        "bases": [base for base, _ in pub.bases()],
        "anomes_cluster": pub.anomes_cluster,
        "algoritmo": ALGORITHM_VERSION, "esquema": SCHEMA_VERSION,
        "trajetoria": {"chave": pub.trajectory,
                       "pasta": store.folder.relative_to(ROOT).as_posix(),
                       "ultimo_mes_materializado": to_anomes(done)},
        "versoes": versions(), "medicoes": measured,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ate", type=int, help="Último AAAAMM a projetar.")
    parser.add_argument("--meses", type=int, default=12, help="Meses após o corte.")
    parser.add_argument("--verificar", action="store_true", help="Não projeta.")
    args = parser.parse_args()
    service = RecommendationService(Settings(_env_file=None))
    started = time.perf_counter()
    pub = service.publication
    loaded = time.perf_counter() - started
    target = period(args.ate) if args.ate else pub.bundle.cutoff + args.meses
    measured: dict[str, object] = {"carga_publicacao_s": round(loaded, 2),
                                   "cpu": os.cpu_count()}
    if not args.verificar:
        before = service.store().last_contiguous(pub.bundle.cutoff)
        state = service.ensure_projection(target)
        t0 = time.perf_counter()
        last_report = 0.0
        while state is not None and any(j["status"] in ("fila", "rodando")
                                        for j in service.job_states()):
            time.sleep(1)
            job = service.job_states()[0]
            if time.perf_counter() - last_report > 30:
                print(f"  {job['meses_calculados']}/{job['meses_necessarios']} meses "
                      f"({time.perf_counter() - t0:.0f} s)", flush=True)
                last_report = time.perf_counter()
        failures = [j for j in service.job_states() if j["status"] == "falhou"]
        if failures:
            raise SystemExit(f"Projeção falhou: {failures[0]['erro']}")
        after = service.store().last_contiguous(pub.bundle.cutoff)
        measured.update({
            "destino": to_anomes(target), "meses_reaproveitados": (before - pub.bundle.cutoff).n,
            "meses_calculados": (after - before).n,
            "projecao_s": round(time.perf_counter() - t0, 2),
        })
    payload = manifest(service, measured)
    out = pub.settings.recomendacoes_run_dir / "manifesto_publicacao.json"
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.replace(temporary, out)
    print(json.dumps(payload["medicoes"], ensure_ascii=False))
    print(f"Manifesto: {out.relative_to(ROOT)}")
    service.shutdown()


if __name__ == "__main__":
    main()
