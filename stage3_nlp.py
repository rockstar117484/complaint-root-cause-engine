"""Stage 3: deterministic, privacy-conscious NLP theme discovery.

Reads the existing processed Parquet dataset and writes aggregate outputs only.
It does not modify source data or any Stage 1/2/2.5 files.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = ["complaint_id", "date_received", "product", "issue", "company", "narrative"]
SAMPLE_SIZE = 30_000
N_CLUSTERS = 6
RANDOM_SEED = 42
HASH_MODULUS = 1000
HASH_CUTOFF = 35  # approximately 3.5% of rows, sampled across the full dataset


def clean_narrative(value: object) -> str:
    """Normalize whitespace and null-like values without exporting the text."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).split())


def select_sample(dataset, sample_size: int = SAMPLE_SIZE) -> pd.DataFrame:
    """Select a reproducible sample across all Parquet fragments using ID hashes."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(dataset.schema.names))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    selected: list[pd.DataFrame] = []
    columns = REQUIRED_COLUMNS
    scanner = dataset.scanner(columns=columns, batch_size=25_000)
    for batch in scanner.to_batches():
        frame = batch.to_pandas()
        frame["narrative"] = frame["narrative"].map(clean_narrative)
        frame = frame[frame["narrative"].str.len() >= 30]
        if frame.empty:
            continue
        # Hash complaint IDs so the sample is spread across the complete dataset,
        # rather than being biased toward the first Parquet row groups.
        hashes = pd.util.hash_pandas_object(frame["complaint_id"].astype(str), index=False)
        frame = frame[(hashes % HASH_MODULUS) < HASH_CUTOFF]
        if not frame.empty:
            selected.append(frame)

    if not selected:
        raise ValueError("No eligible narratives were found in the Parquet dataset.")

    sample = pd.concat(selected, ignore_index=True).drop_duplicates("complaint_id")
    if len(sample) > sample_size:
        sample = sample.sample(n=sample_size, random_state=RANDOM_SEED)
    if len(sample) < N_CLUSTERS:
        raise ValueError(f"Only {len(sample)} eligible narratives found; need at least {N_CLUSTERS}.")
    return sample.reset_index(drop=True)


def build_features(texts: pd.Series):
    """Create TF-IDF unigram/bigram features with bounded vocabulary size."""
    custom_stop_words = set(ENGLISH_STOP_WORDS) | {
        "xxxx", "xx", "xxx", "account", "company", "said", "told", "would", "could"
    }
    vectorizer = TfidfVectorizer(
        stop_words=sorted(custom_stop_words),
        ngram_range=(1, 2),
        min_df=5,
        max_df=0.90,
        max_features=20_000,
        strip_accents="unicode",
        sublinear_tf=True,
        dtype=np.float32,
    )
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def create_cluster_profiles(sample: pd.DataFrame, labels: np.ndarray, model: MiniBatchKMeans,
                             terms: np.ndarray) -> pd.DataFrame:
    """Summarize clusters using terms and metadata, never narrative text."""
    records: list[dict] = []
    for cluster_id in range(model.n_clusters):
        mask = labels == cluster_id
        if not mask.any():
            continue
        top_terms = terms[np.argsort(model.cluster_centers_[cluster_id])[-12:][::-1]]
        subset = sample.loc[mask]
        products = subset["product"].fillna("[MISSING]").value_counts().head(3)
        issues = subset["issue"].fillna("[MISSING]").value_counts().head(3)
        records.append({
            "cluster_id": int(cluster_id),
            "sample_complaints": int(mask.sum()),
            "sample_share_pct": round(float(mask.mean() * 100), 2),
            "top_terms": " | ".join(top_terms.tolist()),
            "leading_products": " | ".join(f"{name} ({count})" for name, count in products.items()),
            "leading_issues": " | ".join(f"{name} ({count})" for name, count in issues.items()),
        })
    return pd.DataFrame(records).sort_values("sample_complaints", ascending=False).reset_index(drop=True)


def run(output_dir: Path | None = None, sample_size: int = SAMPLE_SIZE) -> dict:
    dataset_path = ROOT / "data" / "processed" / "complaints_parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Processed Parquet dataset not found: {dataset_path}. Complete ingestion first."
        )
    import pyarrow.dataset as ds
    dataset = ds.dataset(str(dataset_path), format="parquet")
    sample = select_sample(dataset, sample_size=sample_size)
    vectorizer, matrix = build_features(sample["narrative"])

    cluster_count = min(N_CLUSTERS, matrix.shape[0])
    model = MiniBatchKMeans(
        n_clusters=cluster_count,
        random_state=RANDOM_SEED,
        batch_size=1024,
        n_init=3,
        max_iter=100,
    )
    labels = model.fit_predict(matrix)
    terms = np.asarray(vectorizer.get_feature_names_out())
    profiles = create_cluster_profiles(sample, labels, model, terms)

    out = output_dir or (ROOT / "reports" / "nlp")
    out.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(out / "cluster_profiles.csv", index=False)

    sample["cluster_id"] = labels
    sample["month"] = pd.to_datetime(sample["date_received"], errors="coerce").dt.to_period("M").astype(str)
    sample.groupby(["month", "cluster_id"]).size().rename("sample_complaints").reset_index().to_csv(
        out / "cluster_monthly_trends.csv", index=False
    )
    sample.groupby(["cluster_id", "product"], dropna=False).size().rename("sample_complaints").reset_index().to_csv(
        out / "cluster_product_mix.csv", index=False
    )

    summary = {
        "sample_records": int(len(sample)),
        "tfidf_features": int(matrix.shape[1]),
        "clusters_requested": N_CLUSTERS,
        "clusters_created": int(cluster_count),
        "random_seed": RANDOM_SEED,
        "sampling_method": "deterministic complaint-ID hash filter across all Parquet batches, then seeded cap",
        "raw_narratives_exported": False,
        "limitations": [
            "Clusters are exploratory text groupings, not verified causal root causes.",
            "Cluster sample shares are not population complaint rates.",
            "Top terms and metadata require human review before assigning business labels.",
            "No customer or account exposure denominators are available.",
        ],
    }
    (out / "nlp_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Stage 3 — Complaint Theme Discovery", "",
        f"- Sample records: {len(sample):,}",
        f"- TF-IDF features: {matrix.shape[1]:,}",
        f"- Clusters created: {cluster_count}",
        "- Method: TF-IDF unigrams/bigrams + MiniBatchKMeans",
        "- Raw complaint narratives exported: No", "",
        "## Cluster profiles", "",
        "| Cluster | Sample complaints | Share | Top terms | Leading products |",
        "|---:|---:|---:|---|---|",
    ]
    for row in profiles.to_dict("records"):
        lines.append(
            f"| {row['cluster_id']} | {row['sample_complaints']:,} | {row['sample_share_pct']:.2f}% | "
            f"{row['top_terms']} | {row['leading_products']} |"
        )
    lines += ["", "## Interpretation safeguards", *[f"- {item}" for item in summary["limitations"]]]
    (out / "nlp_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Stage 3 completed: {len(sample):,} narratives, {matrix.shape[1]:,} TF-IDF features, {cluster_count} clusters.")
    print(f"Aggregate outputs saved to: {out}")
    return summary


if __name__ == "__main__":
    run()
