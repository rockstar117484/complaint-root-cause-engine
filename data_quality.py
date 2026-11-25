"""Data-quality audit for the processed CFPB Parquet dataset.

Run:
    python -m src.data_quality

The scan is batch-based and does not load all complaint narratives into RAM.
It writes a Markdown and JSON report under reports/.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.dataset as ds
import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = [
    "complaint_id", "date_received", "product", "narrative",
    "company_response_to_consumer",
]
EXPECTED_OUTCOMES = {
    "Closed with explanation",
    "Closed with non-monetary relief",
    "Closed with monetary relief",
    "Untimely response",
    "In progress",
}


def load_config() -> dict[str, Any]:
    with (ROOT / "config.yaml").open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def get_dataset(path: Path) -> ds.Dataset:
    if not path.exists():
        raise FileNotFoundError(
            f"Processed Parquet dataset not found: {path}. Run ingestion first."
        )
    dataset = ds.dataset(str(path), format="parquet")
    available = set(dataset.schema.names)
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        raise ValueError(f"Parquet dataset is missing required columns: {missing}")
    return dataset


def audit_dataset(
    dataset_path: Path,
    output_dir: Path,
    chunksize: int = 25_000,
    start_date: str = "2024-06-01",
    end_date: str = "2026-05-31",
) -> dict[str, Any]:
    """Run row, schema, null, ID uniqueness, date, label and narrative checks."""
    dataset = get_dataset(dataset_path)
    schema = [{"name": field.name, "type": str(field.type), "nullable": field.nullable}
              for field in dataset.schema]
    columns = dataset.schema.names

    output_dir.mkdir(parents=True, exist_ok=True)
    id_db = output_dir / "data_quality_ids.sqlite"
    if id_db.exists():
        id_db.unlink()
    conn = sqlite3.connect(id_db)
    conn.execute("CREATE TABLE ids (complaint_id TEXT PRIMARY KEY)")

    row_count = 0
    null_counts: Counter = Counter()
    blank_counts: Counter = Counter()
    outcome_counts: Counter = Counter()
    product_counts: Counter = Counter()
    source_counts: Counter = Counter()
    month_counts: Counter = Counter()
    state_counts: Counter = Counter()
    narrative_length_sum = 0
    narrative_length_min = None
    narrative_length_max = 0
    narrative_length_count = 0
    invalid_date_count = 0
    out_of_window_count = 0
    invalid_outcome_count = 0
    missing_months: list[str] = []
    min_date = None
    max_date = None
    duplicate_ids = 0
    id_rows_seen = 0

    scan_cols = list(dict.fromkeys(
        columns + ["complaint_id", "date_received", "narrative",
                   "company_response_to_consumer", "product", "state", "source_archive"]
    ))
    scan_cols = [c for c in scan_cols if c in columns]
    scanner = dataset.scanner(columns=scan_cols, batch_size=chunksize)

    for batch in scanner.to_batches():
        frame = batch.to_pandas()
        n = len(frame)
        row_count += n

        for col in columns:
            null_counts[col] += int(frame[col].isna().sum())
        for col in columns:
            if pd.api.types.is_string_dtype(frame[col].dtype) or frame[col].dtype == object:
                blank_counts[col] += int(frame[col].dropna().astype(str).str.strip().eq("").sum())

        ids = frame["complaint_id"].dropna().astype(str).str.strip()
        ids = ids[ids.ne("")]
        id_rows_seen += len(ids)
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO ids(complaint_id) VALUES (?)",
            ((value,) for value in ids.tolist()),
        )
        inserted = conn.total_changes - before
        duplicate_ids += len(ids) - inserted

        dates = pd.to_datetime(frame["date_received"], errors="coerce")
        invalid_date_count += int(dates.isna().sum())
        valid_dates = dates.dropna()
        if not valid_dates.empty:
            batch_min, batch_max = valid_dates.min(), valid_dates.max()
            min_date = batch_min if min_date is None else min(min_date, batch_min)
            max_date = batch_max if max_date is None else max(max_date, batch_max)
            out_of_window_count += int(
                (~valid_dates.between(pd.Timestamp(start_date), pd.Timestamp(end_date))).sum()
            )
            months = valid_dates.dt.to_period("M").astype(str)
            month_counts.update(months.value_counts().to_dict())

        outcome = frame["company_response_to_consumer"].fillna("[MISSING]").astype(str).str.strip()
        outcome_counts.update(outcome.value_counts().to_dict())
        invalid_outcome_count += int((~outcome.isin(EXPECTED_OUTCOMES | {"[MISSING]"})).sum())

        product = frame["product"].fillna("[MISSING]").astype(str).str.strip()
        product_counts.update(product.value_counts().to_dict())

        if "source_archive" in frame:
            source = frame["source_archive"].fillna("[MISSING]").astype(str)
            source_counts.update(source.value_counts().to_dict())
        if "state" in frame:
            states = frame["state"].fillna("[MISSING]").astype(str).str.strip()
            state_counts.update(states.value_counts().to_dict())

        narratives = frame["narrative"].fillna("").astype(str)
        lengths = narratives.str.len()
        narrative_length_sum += int(lengths.sum())
        narrative_length_count += len(lengths)
        if len(lengths):
            batch_min_len = int(lengths.min())
            narrative_length_min = batch_min_len if narrative_length_min is None else min(narrative_length_min, batch_min_len)
            narrative_length_max = max(narrative_length_max, int(lengths.max()))

        if row_count % (chunksize * 10) == 0:
            conn.commit()
            print(f"Audited {row_count:,} rows...")

    conn.commit()
    unique_ids = conn.execute("SELECT COUNT(*) FROM ids").fetchone()[0]
    conn.close()

    month_index = pd.period_range(start=start_date[:7], end=end_date[:7], freq="M").astype(str).tolist()
    missing_months = [month for month in month_index if month_counts.get(month, 0) == 0]
    null_report = {
        col: {
            "missing": int(null_counts[col]),
            "missing_pct": round((null_counts[col] / row_count * 100), 4) if row_count else 0.0,
            "blank_strings": int(blank_counts[col]),
        }
        for col in columns
    }

    monetary = int(outcome_counts.get("Closed with monetary relief", 0))
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "dataset_path": str(dataset_path.relative_to(ROOT)) if dataset_path.is_relative_to(ROOT) else str(dataset_path),
        "rows": int(row_count),
        "columns": schema,
        "date_range": {
            "minimum": str(min_date.date()) if min_date is not None else None,
            "maximum": str(max_date.date()) if max_date is not None else None,
            "configured_start": start_date,
            "configured_end": end_date,
            "invalid_dates": int(invalid_date_count),
            "outside_configured_window": int(out_of_window_count),
            "months_missing": missing_months,
        },
        "identifiers": {
            "nonempty_ids_seen": int(id_rows_seen),
            "unique_ids": int(unique_ids),
            "duplicate_ids": int(duplicate_ids),
        },
        "narrative": {
            "empty_or_missing": int(null_counts.get("narrative", 0) + blank_counts.get("narrative", 0)),
            "mean_characters": round(narrative_length_sum / narrative_length_count, 2) if narrative_length_count else None,
            "minimum_characters": narrative_length_min,
            "maximum_characters": narrative_length_max,
        },
        "outcomes": {
            "counts": dict(outcome_counts),
            "unknown_label_rows": int(invalid_outcome_count),
            "monetary_relief_count": monetary,
            "monetary_relief_rate_pct": round(monetary / row_count * 100, 4) if row_count else 0.0,
        },
        "nulls": null_report,
        "top_products": product_counts.most_common(20),
        "top_states": state_counts.most_common(20),
        "source_archive_counts": source_counts.most_common(),
    }

    (output_dir / "data_quality_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Data Quality Report", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Rows audited: {row_count:,}",
        f"- Columns: {len(columns)}",
        f"- Observed date range: {payload['date_range']['minimum']} to {payload['date_range']['maximum']}",
        f"- Unique complaint IDs: {unique_ids:,}",
        f"- Duplicate complaint IDs: {duplicate_ids:,}",
        f"- Invalid dates: {invalid_date_count:,}",
        f"- Rows outside configured window: {out_of_window_count:,}",
        f"- Missing months: {', '.join(missing_months) if missing_months else 'None'}", "",
        "## Field completeness", "",
        "| Field | Missing | Missing % | Blank strings |",
        "|---|---:|---:|---:|",
    ]
    for col, stats in null_report.items():
        lines.append(f"| {col} | {stats['missing']:,} | {stats['missing_pct']:.2f}% | {stats['blank_strings']:,} |")
    lines += [
        "", "## Narrative checks", "",
        f"- Mean narrative length: {payload['narrative']['mean_characters']} characters",
        f"- Minimum narrative length: {narrative_length_min}",
        f"- Maximum narrative length: {narrative_length_max}",
        f"- Empty/missing narratives in processed dataset: {payload['narrative']['empty_or_missing']:,}", "",
        "## Outcome checks", "",
        f"- Monetary relief: {monetary:,} ({payload['outcomes']['monetary_relief_rate_pct']:.2f}%)",
        f"- Unknown outcome labels: {invalid_outcome_count:,}", "",
        "## Top products", "",
        "| Product | Rows |", "|---|---:|",
    ]
    lines += [f"| {name} | {count:,} |" for name, count in product_counts.most_common(20)]
    lines += ["", "## Top states", "", "| State | Rows |", "|---|---:|"]
    lines += [f"| {name} | {count:,} |" for name, count in state_counts.most_common(20)]
    lines += ["", "## Source archive contribution", "", "| Archive | Rows |", "|---|---:|"]
    lines += [f"| {name} | {count:,} |" for name, count in source_counts.most_common()]
    lines += [
        "", "## Interpretation", "",
        "- This report audits the already-filtered narrative dataset; it cannot measure narrative availability among all source rows.",
        "- A missing sub-issue, tag, public response, state, or ZIP code is not automatically an error; these fields may be optional or unavailable.",
        "- Complaint records are self-selected and published narratives are a selected subset.",
        "- A zero duplicate count is a result of this audit, not proof that the source archives are universally non-overlapping.",
    ]
    (output_dir / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    config = load_config()
    d = config["data"]
    audit_dataset(
        ROOT / d["parquet_dir"],
        ROOT / d["reports_dir"],
        int(d.get("chunksize", 25_000)),
        d["start_date"],
        d["end_date"],
    )
    print("Data quality audit complete: reports/data_quality_report.md")


if __name__ == "__main__":
    main()
