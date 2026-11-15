"""Fixtures compartilhadas dos testes da API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """Cria datasets temporários cobrindo CSV, Parquet, sidecar e arquivo corrompido."""
    root = tmp_path / "tratados"
    root.mkdir()

    locais = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6],
            "nome": [
                "Atacama",
                "Askja",
                "Dry Valleys",
                "Devon",
                "Lanzarote",
                "Mojave",
            ],
            "pais": ["Chile", "Islandia", "Antartida", "Canada", "Espanha", "EUA"],
            "clima": ["arido", "frio", "polar", "polar", "arido", "arido"],
            "score": [0.91, 0.77, 0.65, 0.60, 0.82, float("nan")],
            "latitude": [-23.5, 65.0, -77.5, 75.3, 29.0, 35.0],
            "ativo": [True, True, False, False, True, False],
        }
    )
    locais.to_csv(root / "locais.csv", index=False)

    clusters = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "cluster": [0, 1, 1],
            "score": [0.5, 0.7, 0.9],
            "observado_em": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "peso": [float("nan"), 1.5, 2.5],
        }
    )
    clusters.to_parquet(root / "clusters.parquet", index=False)

    nested = root / "case1"
    nested.mkdir()
    pd.DataFrame({"id": ["r1", "r2"], "score": [0.2, 0.8]}).to_csv(
        nested / "ranking.csv", index=False
    )

    (root / "vazio.csv").write_text("id,nome\n", encoding="utf-8")
    (root / "corrompido.parquet").write_bytes(b"isto nao e um parquet")
    (root / "notas.txt").write_text("ignorado", encoding="utf-8")

    sidecar = {
        "description": "Análogos terrestres de referência.",
        "id_column": "id",
        "tags": ["análogos", "terrestres"],
        "source": "ETL",
        "columns": {"score": "Similaridade entre 0 e 1."},
    }
    (root / "locais.meta.json").write_text(
        json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
    )
    return root


@pytest.fixture()
def models_dir(tmp_path: Path) -> Path:
    """Cria artefatos fictícios e sidecars de modelo."""
    root = tmp_path / "models"
    root.mkdir()

    (root / "cluster_kmeans.joblib").write_bytes(b"fake-joblib")
    (root / "cluster_kmeans.meta.json").write_text(
        json.dumps(
            {
                "description": "KMeans dos análogos terrestres.",
                "tags": ["clusterização"],
                "algorithm": "KMeans",
                "framework": "scikit-learn",
                "target": "cluster",
                "trained_at": "2026-11-01",
                "metrics": {"silhouette": 0.42},
                "params": {"n_clusters": 4},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    nested = root / "previsao"
    nested.mkdir()
    (nested / "xgboost.ubj").write_bytes(b"fake-ubj")
    return root


@pytest.fixture()
def settings(data_dir: Path, models_dir: Path) -> Settings:
    """Configuração isolada, apontando para diretórios temporários."""
    return Settings(
        _env_file=None,
        environment="test",
        data_dir=data_dir,
        models_dir=models_dir,
        cors_origins=["http://frontend.test"],
        default_limit=100,
        max_limit=1_000,
        max_fields=4,
        aggregation_default_limit=100,
        aggregation_max_limit=1_000,
        cache_max_entries=8,
    )


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    """Cliente HTTP com exceções do servidor convertidas pelo handler global."""
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client
