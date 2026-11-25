"""Shared utilities for Stage 2.5 analytics."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict[str, Any]:
    with (ROOT / "config.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def configured_dataset() -> tuple[Path, Path, int]:
    config = load_config()["data"]
    return (
        ROOT / config["parquet_dir"],
        ROOT / config["reports_dir"] / "advanced_analytics",
        int(config.get("chunksize", 25_000)),
    )


def open_dataset(path: Path) -> ds.Dataset:
    if not path.exists():
        raise FileNotFoundError(
            f"Parquet dataset not found: {path}. Complete ingestion first."
        )
    return ds.dataset(str(path), format="parquet")


def require_columns(dataset: ds.Dataset, required: list[str]) -> None:
    missing = sorted(set(required) - set(dataset.schema.names))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_label(series):
    return series.fillna("[MISSING]").astype(str).str.strip().replace("", "[MISSING]")


def write_csv(rows: list[dict], path: Path, columns: list[str] | None = None) -> None:
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
