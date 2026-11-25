"""Privacy-conscious narrative diagnostics for NLP readiness.

Run:
    python -m src.text_diagnostics

The module does not export raw complaint narratives. Exact duplicate detection
uses a disk-backed SQLite hash index. Near-duplicate review is deliberately
not claimed; that requires a separately designed, privacy-aware similarity step.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sqlite3

import pandas as pd

from src.analytics_common import (
    configured_dataset, open_dataset, require_columns, utc_now, write_csv
)


def normalize_for_hash(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def run_text_diagnostics(
    dataset_path: Path,
    output_dir: Path,
    batch_size: int = 25_000,
) -> dict:
    dataset = open_dataset(dataset_path)
    require_columns(dataset, ["complaint_id", "narrative", "product"])
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "narrative_hash_index.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE narrative_hashes (hash TEXT PRIMARY KEY, first_complaint_id TEXT, occurrences INTEGER NOT NULL DEFAULT 1)")

    total = 0
    char_sum = 0
    word_sum = 0
    min_chars = None
    max_chars = 0
    char_bins = Counter()
    word_bins = Counter()
    product_lengths = Counter()
    blank_narratives = 0
    exact_duplicate_rows = 0
    unique_hashes = 0
    processed_hashes = 0

    columns = ["complaint_id", "narrative", "product"]
    for batch in dataset.scanner(columns=columns, batch_size=batch_size).to_batches():
        frame = batch.to_pandas()
        total += len(frame)
        narratives = frame["narrative"].fillna("").astype(str)
        products = frame["product"].fillna("[MISSING]").astype(str).str.strip()
        ids = frame["complaint_id"].fillna("").astype(str)
        lengths = narratives.str.len()
        words = narratives.str.split().str.len()

        char_sum += int(lengths.sum())
        word_sum += int(words.sum())
        if len(lengths):
            min_chars = int(lengths.min()) if min_chars is None else min(min_chars, int(lengths.min()))
            max_chars = max(max_chars, int(lengths.max()))
        blank_narratives += int(narratives.str.strip().eq("").sum())

        char_labels = pd.cut(
            lengths, bins=[-1, 0, 50, 100, 250, 500, 1000, 2000, 5000, float("inf")],
            labels=["0", "1-50", "51-100", "101-250", "251-500", "501-1000", "1001-2000", "2001-5000", "5000+"],
            include_lowest=True,
        )
        word_labels = pd.cut(
            words, bins=[-1, 0, 10, 25, 50, 100, 250, 500, float("inf")],
            labels=["0", "1-10", "11-25", "26-50", "51-100", "101-250", "251-500", "500+"],
            include_lowest=True,
        )
        char_bins.update(char_labels.astype(str).value_counts().to_dict())
        word_bins.update(word_labels.astype(str).value_counts().to_dict())

        for product, length, word_count in zip(products, lengths, words):
            product_lengths[(product, int(length // 100) * 100, int(word_count // 25) * 25)] += 1

        records = []
        for complaint_id, narrative in zip(ids, narratives):
            normalized = normalize_for_hash(narrative)
            if not normalized:
                continue
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            records.append((digest, complaint_id))
        before = conn.total_changes
        conn.executemany(
            "INSERT INTO narrative_hashes(hash, first_complaint_id, occurrences) VALUES (?, ?, 1) "
            "ON CONFLICT(hash) DO UPDATE SET occurrences = occurrences + 1",
            records,
        )
        inserted_or_updated = conn.total_changes - before
        # Every processed nonblank narrative beyond the first occurrence is a duplicate row.
        processed_hashes += len(records)
        if total % (batch_size * 10) == 0:
            conn.commit()
            print(f"Checked {total:,} narratives...")

    conn.commit()
    unique_hashes = conn.execute("SELECT COUNT(*) FROM narrative_hashes").fetchone()[0]
    duplicate_groups = conn.execute(
        "SELECT COUNT(*) FROM narrative_hashes WHERE occurrences > 1"
    ).fetchone()[0]
    duplicate_rows = conn.execute(
        "SELECT COALESCE(SUM(occurrences - 1), 0) FROM narrative_hashes WHERE occurrences > 1"
    ).fetchone()[0]
    conn.close()

    char_rows = [{"length_band": label, "narratives": int(count)} for label, count in char_bins.items()]
    word_rows = [{"word_count_band": label, "narratives": int(count)} for label, count in word_bins.items()]
    product_rows = [
        {"product": product, "character_length_bucket": char_bucket,
         "word_count_bucket": word_bucket, "narratives": int(count)}
        for (product, char_bucket, word_bucket), count in product_lengths.items()
    ]
    write_csv(char_rows, output_dir / "narrative_character_length_bands.csv", ["length_band", "narratives"])
    write_csv(word_rows, output_dir / "narrative_word_count_bands.csv", ["word_count_band", "narratives"])
    write_csv(product_rows, output_dir / "product_narrative_length_buckets.csv",
              ["product", "character_length_bucket", "word_count_bucket", "narratives"])

    payload = {
        "generated_at_utc": utc_now(),
        "records_analysed": total,
        "blank_narratives": blank_narratives,
        "mean_characters": round(char_sum / total, 2) if total else None,
        "mean_words": round(word_sum / total, 2) if total else None,
        "minimum_characters": min_chars,
        "maximum_characters": max_chars,
        "nonblank_narratives_hashed": processed_hashes,
        "unique_normalized_narrative_hashes": int(unique_hashes),
        "exact_duplicate_groups": int(duplicate_groups),
        "exact_duplicate_rows_beyond_first": int(duplicate_rows),
        "exact_duplicate_rate_pct": round(duplicate_rows / processed_hashes * 100, 4) if processed_hashes else 0.0,
        "hash_normalization": "casefold, collapse whitespace, remove punctuation; SHA-256",
        "privacy_note": "Raw narratives and hashes are not exported to CSV or Markdown. The SQLite hash index is local and must not be committed.",
        "limitation": "This detects exact duplicates after normalization, not semantic or near-duplicates.",
    }
    (output_dir / "text_diagnostics_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report = [
        "# Narrative Text Diagnostics", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Records analysed: {total:,}",
        f"- Blank narratives: {blank_narratives:,}",
        f"- Mean characters: {payload['mean_characters']}",
        f"- Mean words: {payload['mean_words']}",
        f"- Minimum characters: {min_chars}",
        f"- Maximum characters: {max_chars}",
        f"- Exact duplicate groups: {duplicate_groups:,}",
        f"- Duplicate rows beyond first: {duplicate_rows:,} ({payload['exact_duplicate_rate_pct']:.2f}%)", "",
        "## Interpretation safeguards", "",
        "- Repeated narratives can arise from templates, copied text, or repeated consumer wording; duplicates are not automatically invalid complaints.",
        "- Normalization is case-insensitive, collapses whitespace, and removes punctuation before hashing.",
        "- This check does not detect near-duplicates or semantic similarity.",
        "- Raw narratives are not included in reports to reduce exposure of potentially sensitive personal information.",
        "- Review the duplicate rate by product and source if a more detailed investigation is needed; do not automatically delete duplicates.",
    ]
    (output_dir / "text_diagnostics_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    dataset_path, output_dir, batch_size = configured_dataset()
    result = run_text_diagnostics(dataset_path, output_dir, batch_size)
    print(f"Text diagnostics complete: {output_dir / 'text_diagnostics_report.md'}")
    print(f"Exact duplicate rate: {result['exact_duplicate_rate_pct']:.2f}%")


if __name__ == "__main__":
    main()
