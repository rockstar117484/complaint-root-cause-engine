"""Stream multiple CFPB ZIP exports into a deduplicated Parquet dataset.

Validate: python -m src.ingest_archives --validate-only
Ingest:   python -m src.ingest_archives --run

Source ZIPs are never extracted or modified. SQLite provides disk-backed
global deduplication by Complaint ID.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "complaint_id", "date_received", "product", "sub_product", "issue",
    "sub_issue", "narrative", "company_public_response", "company", "state",
    "zip_code", "tags", "submitted_via", "date_sent_to_company",
    "company_response_to_consumer", "timely_response", "source_archive",
]


def load_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration."""
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def normalise_header(value: str) -> str:
    """Normalise header punctuation, spaces and case for alias matching."""
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def resolve_columns(headers: list[str], aliases: dict[str, list[str]]) -> dict[str, str | None]:
    """Map canonical field names to source headers."""
    actual = {normalise_header(header): header for header in headers}
    result = {}
    for canonical, candidates in aliases.items():
        result[canonical] = next(
            (actual[normalise_header(candidate)]
             for candidate in candidates
             if normalise_header(candidate) in actual),
            None,
        )
    return result


def discover_archives(raw_dir: Path) -> list[Path]:
    """Discover ZIP files directly inside data/raw in stable order."""
    archives = sorted(p for p in raw_dir.glob("*.zip") if p.is_file())
    if not archives:
        raise FileNotFoundError(
            f"No ZIP archives found in {raw_dir}. Place all downloaded CFPB ZIPs there."
        )
    return archives


def get_csv_member(archive: zipfile.ZipFile, path: Path) -> str:
    """Require exactly one CSV member rather than silently choosing one."""
    members = [
        item.filename for item in archive.infolist()
        if not item.is_dir() and item.filename.lower().endswith(".csv")
    ]
    if len(members) != 1:
        raise ValueError(
            f"{path.name}: expected exactly one CSV inside ZIP, found {len(members)}: {members}"
        )
    return members[0]


def inspect_archive(path: Path, aliases: dict[str, list[str]]) -> dict[str, Any]:
    """Read ZIP metadata and the CSV header only."""
    with zipfile.ZipFile(path) as archive:
        member = get_csv_member(archive, path)
        with archive.open(member) as stream:
            header_line = stream.readline().decode("utf-8-sig", errors="replace")
        headers = next(csv.reader([header_line]))
        mapping = resolve_columns(headers, aliases)
        required = ["complaint_id", "date_received", "product", "narrative",
                    "company_response_to_consumer"]
        missing = [field for field in required if mapping.get(field) is None]
        return {
            "archive": path.name,
            "csv_member": member,
            "compressed_bytes": path.stat().st_size,
            "uncompressed_csv_bytes": archive.getinfo(member).file_size,
            "headers": headers,
            "mapping": mapping,
            "missing_required_fields": missing,
            "valid_schema": not missing,
        }


def read_zip_chunks(path: Path, member: str, columns: list[str], chunksize: int) -> Iterator[pd.DataFrame]:
    """Stream CSV chunks from a ZIP member without extracting the file."""
    import io
    with zipfile.ZipFile(path) as archive:
        with archive.open(member) as binary:
            text_stream = io.TextIOWrapper(
                binary, encoding="utf-8-sig", errors="replace", newline=""
            )
            reader = pd.read_csv(
                text_stream, chunksize=chunksize, dtype="string",
                usecols=columns, low_memory=False, on_bad_lines="error",
            )
            try:
                yield from reader
            finally:
                reader.close()
                text_stream.detach()


def create_staging_db(path: Path) -> sqlite3.Connection:
    """Create a disk-backed SQLite table with globally unique complaint IDs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("""
        CREATE TABLE complaints (
            complaint_id TEXT PRIMARY KEY,
            date_received TEXT, product TEXT, sub_product TEXT, issue TEXT,
            sub_issue TEXT, narrative TEXT, company_public_response TEXT,
            company TEXT, state TEXT, zip_code TEXT, tags TEXT,
            submitted_via TEXT, date_sent_to_company TEXT,
            company_response_to_consumer TEXT, timely_response TEXT,
            source_archive TEXT
        )
    """)
    return connection


def canonicalise_chunk(
    chunk: pd.DataFrame,
    mapping: dict[str, str | None],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, Counter]:
    """Standardise a chunk and apply ID, date-window and narrative checks."""
    stats = Counter()
    data = pd.DataFrame(index=chunk.index)
    for field in FIELDS:
        if field == "source_archive":
            continue
        source = mapping.get(field)
        data[field] = chunk[source] if source and source in chunk.columns else pd.NA

    stats["rows_read"] = len(data)
    data["complaint_id"] = data["complaint_id"].astype("string").str.strip()
    valid_id = data["complaint_id"].notna() & data["complaint_id"].ne("")
    stats["missing_id"] = int((~valid_id).sum())
    data = data.loc[valid_id].copy()

    parsed = pd.to_datetime(data["date_received"], errors="coerce")
    stats["invalid_date"] = int(parsed.isna().sum())
    in_window = parsed.notna() & parsed.between(start, end)
    stats["outside_date_window"] = int((parsed.notna() & ~in_window).sum())
    data = data.loc[in_window].copy()
    parsed = parsed.loc[in_window]
    data["date_received"] = parsed.dt.strftime("%Y-%m-%d")

    sent = pd.to_datetime(data["date_sent_to_company"], errors="coerce")
    data["date_sent_to_company"] = sent.dt.strftime("%Y-%m-%d")

    data["narrative"] = data["narrative"].fillna("").astype("string").str.strip()
    has_text = data["narrative"].ne("")
    stats["missing_narrative"] = int((~has_text).sum())
    data = data.loc[has_text].copy()

    for field in FIELDS:
        if field not in ("source_archive", "date_received", "date_sent_to_company"):
            data[field] = data[field].astype("string").str.strip().replace("", pd.NA)

    stats["eligible_before_dedup"] = len(data)
    return data, stats


def insert_rows(connection: sqlite3.Connection, frame: pd.DataFrame, archive_name: str) -> tuple[int, int]:
    """Insert rows and let SQLite skip duplicate IDs across all archives."""
    if frame.empty:
        return 0, 0
    frame = frame.copy()
    frame["source_archive"] = archive_name
    placeholders = ",".join("?" for _ in FIELDS)
    sql = f"INSERT OR IGNORE INTO complaints ({','.join(FIELDS)}) VALUES ({placeholders})"
    values = [
        tuple(None if pd.isna(value) else str(value) for value in row)
        for row in frame[FIELDS].itertuples(index=False, name=None)
    ]
    before = connection.total_changes
    connection.executemany(sql, values)
    inserted = connection.total_changes - before
    return inserted, len(values) - inserted


def export_parquet(connection: sqlite3.Connection, output_dir: Path, chunksize: int) -> int:
    """Write a folder of Parquet parts without loading all rows into RAM."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    query = f"SELECT {','.join(FIELDS)} FROM complaints ORDER BY date_received, complaint_id"
    total = 0
    for index, frame in enumerate(pd.read_sql_query(query, connection, chunksize=chunksize)):
        frame.to_parquet(output_dir / f"part-{index:05d}.parquet",
                         index=False, engine="pyarrow", compression="snappy")
        total += len(frame)
    return total


def write_reports(
    connection: sqlite3.Connection,
    report_dir: Path,
    archive_reports: list[dict[str, Any]],
    counters: Counter,
    duplicates: int,
    total: int,
    config: dict[str, Any],
) -> None:
    """Write JSON and Markdown summaries from the staged data."""
    report_dir.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_sql_query(
        "SELECT substr(date_received,1,7) month, COUNT(*) complaints "
        "FROM complaints GROUP BY month ORDER BY month", connection)
    outcomes = pd.read_sql_query(
        "SELECT COALESCE(company_response_to_consumer,'[MISSING]') outcome, COUNT(*) complaints "
        "FROM complaints GROUP BY outcome ORDER BY complaints DESC", connection)
    products = pd.read_sql_query(
        "SELECT COALESCE(product,'[MISSING]') product, COUNT(*) complaints "
        "FROM complaints GROUP BY product ORDER BY complaints DESC LIMIT 20", connection)
    missing_fields = [f for f in FIELDS if f != "source_archive"]
    missing_sql = ", ".join(
        f"SUM(CASE WHEN {f} IS NULL OR TRIM({f})='' THEN 1 ELSE 0 END) AS {f}"
        for f in missing_fields
    )
    missing = pd.read_sql_query(f"SELECT {missing_sql} FROM complaints", connection).iloc[0].to_dict()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "date_window": {"start": config["data"]["start_date"], "end": config["data"]["end_date"]},
        "archive_count": len(archive_reports),
        "archives": archive_reports,
        "processing_counters": dict(counters),
        "duplicate_ids_skipped": duplicates,
        "final_unique_complaints": total,
        "monthly_counts": monthly.to_dict(orient="records"),
        "outcome_distribution": outcomes.to_dict(orient="records"),
        "top_products": products.to_dict(orient="records"),
        "missing_values_in_final_dataset": {k: int(v or 0) for k, v in missing.items()},
    }
    (report_dir / "ingestion_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# CFPB Ingestion Report", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Date window: {payload['date_window']['start']} to {payload['date_window']['end']}",
        f"- ZIP archives validated: {len(archive_reports)}",
        f"- Unique complaints retained: {total:,}",
        f"- Duplicate complaint IDs skipped: {duplicates:,}", "",
        "## Processing counters", "", "| Counter | Rows |", "|---|---:|",
    ]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(counters.items())]
    lines += ["", "## Monthly coverage", "", "| Month | Complaints |", "|---|---:|"]
    lines += [f"| {r.month} | {int(r.complaints):,} |" for r in monthly.itertuples(index=False)]
    lines += ["", "## Company response outcomes", "", "| Outcome | Complaints |", "|---|---:|"]
    lines += [f"| {r.outcome} | {int(r.complaints):,} |" for r in outcomes.itertuples(index=False)]
    lines += ["", "## Top products", "", "| Product | Complaints |", "|---|---:|"]
    lines += [f"| {r.product} | {int(r.complaints):,} |" for r in products.itertuples(index=False)]
    lines += ["", "## Missing values", "", "| Field | Missing rows |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in payload["missing_values_in_final_dataset"].items()]
    lines += [
        "", "## Interpretation and limitations", "",
        "- These are published CFPB complaint records, not a representative sample of all consumers.",
        "- Only rows with an ID, parseable date inside the configured window, and non-empty narrative are retained.",
        "- Duplicate IDs: first eligible record encountered in alphabetical archive filename order is retained.",
        "- Complaint counts alone do not establish causation or market-wide incidence.",
    ]
    (report_dir / "ingestion_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(validate_only: bool) -> int:
    config = load_config(ROOT / "config.yaml")
    dcfg = config["data"]
    archives = discover_archives(ROOT / dcfg["raw_dir"])
    expected = dcfg.get("expected_archive_count")
    if expected and len(archives) != int(expected):
        print(f"WARNING: expected {expected} ZIPs; found {len(archives)}. Verify before proceeding.")

    reports = []
    for i, path in enumerate(archives, 1):
        print(f"[{i}/{len(archives)}] Validating {path.name}")
        info = inspect_archive(path, config["columns"])
        if not info["valid_schema"]:
            raise ValueError(f"{path.name}: missing required fields {info['missing_required_fields']}")
        reports.append(info)
        print(f"    OK | compressed size {info['compressed_bytes']/1_000_000:.1f} MB")

    if validate_only:
        output = ROOT / dcfg["reports_dir"] / "archive_validation.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
        print(f"Validation passed. Report: {output.relative_to(ROOT)}")
        return 0

    db_path = ROOT / dcfg["staging_db"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in [db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]:
        if candidate.exists():
            candidate.unlink()

    conn = create_staging_db(db_path)
    counters = Counter()
    duplicate_count = 0
    try:
        start, end = pd.Timestamp(dcfg["start_date"]), pd.Timestamp(dcfg["end_date"])
        for i, (path, info) in enumerate(zip(archives, reports), 1):
            print(f"\n[{i}/{len(archives)}] Ingesting {path.name}")
            mapping = info["mapping"]
            selected_cols = sorted({v for v in mapping.values() if v})
            for chunk_no, chunk in enumerate(
                read_zip_chunks(path, info["csv_member"], selected_cols, int(dcfg["chunksize"])), 1
            ):
                standard, stats = canonicalise_chunk(chunk, mapping, start, end)
                counters.update(stats)
                inserted, duplicates = insert_rows(conn, standard, path.name)
                counters["inserted_unique"] += inserted
                counters["duplicate_ids"] += duplicates
                duplicate_count += duplicates
                if chunk_no % 10 == 0:
                    conn.commit()
                    print(f"    chunks {chunk_no:,}; unique retained {counters['inserted_unique']:,}")
            conn.commit()

        total = export_parquet(conn, ROOT / dcfg["parquet_dir"], int(dcfg["chunksize"]))
        write_reports(conn, ROOT / dcfg["reports_dir"], reports,
                      counters, duplicate_count, total, config)
    finally:
        conn.close()

    print("\nINGESTION COMPLETE")
    print(f"Unique complaints: {total:,}")
    print(f"Duplicate IDs skipped: {duplicate_count:,}")
    print(f"Parquet: {dcfg['parquet_dir']}")
    print(f"Report: {dcfg['reports_dir']}/ingestion_report.md")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest multiple CFPB historical ZIP exports.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only", action="store_true")
    group.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        return run(validate_only=args.validate_only)
    except Exception as exc:
        print(f"\nINGESTION ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Source ZIPs were not modified. Check the named archive, disk space and schema.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
