"""Exploratory data analysis for the processed CFPB narrative dataset.

Run:
    python -m src.eda

Outputs aggregated CSV tables and an EDA JSON summary under reports/eda/.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict[str, Any]:
    with (ROOT / "config.yaml").open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def safe_label(series: pd.Series) -> pd.Series:
    return series.fillna("[MISSING]").astype(str).str.strip().replace("", "[MISSING]")


def scan_eda(dataset_path: Path, output_dir: Path, chunksize: int = 25_000) -> dict[str, Any]:
    """Aggregate key EDA dimensions batch-wise to keep memory bounded."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Parquet dataset not found: {dataset_path}")
    dataset = ds.dataset(str(dataset_path), format="parquet")
    wanted = [
        "date_received", "product", "sub_product", "issue", "sub_issue",
        "company", "state", "submitted_via", "company_response_to_consumer",
        "timely_response", "narrative", "source_archive",
    ]
    columns = [col for col in wanted if col in dataset.schema.names]
    required = ["date_received", "product", "issue", "company", "narrative", "company_response_to_consumer"]
    missing = [col for col in required if col not in columns]
    if missing:
        raise ValueError(f"Dataset missing EDA-required columns: {missing}")

    counters: dict[str, Counter] = {col: Counter() for col in columns if col not in {"narrative", "date_received"}}
    monthly_counts = Counter()
    narrative_lengths = Counter()
    monthly_outcomes = Counter()
    product_outcomes = Counter()
    total = 0
    length_sum = 0
    length_min = None
    length_max = 0

    for batch in dataset.scanner(columns=columns, batch_size=chunksize).to_batches():
        frame = batch.to_pandas()
        total += len(frame)
        for col in counters:
            values = safe_label(frame[col])
            counters[col].update(values.value_counts().to_dict())

        dates = pd.to_datetime(frame["date_received"], errors="coerce")
        month = dates.dt.to_period("M").astype(str)
        monthly_counts.update(month.value_counts().to_dict())
        outcomes = safe_label(frame["company_response_to_consumer"])
        products = safe_label(frame["product"])
        monthly_outcomes.update((m, o) for m, o in zip(month, outcomes))
        product_outcomes.update((p, o) for p, o in zip(products, outcomes))

        lengths = frame["narrative"].fillna("").astype(str).str.len()
        length_sum += int(lengths.sum())
        if len(lengths):
            length_min = int(lengths.min()) if length_min is None else min(length_min, int(lengths.min()))
            length_max = max(length_max, int(lengths.max()))
        bins = pd.cut(
            lengths,
            bins=[-1, 0, 50, 100, 250, 500, 1000, 2000, 5000, float("inf")],
            labels=["0", "1-50", "51-100", "101-250", "251-500",
                    "501-1000", "1001-2000", "2001-5000", "5000+"],
            include_lowest=True,
        )
        narrative_lengths.update(bins.astype(str).value_counts().to_dict())

    output_dir.mkdir(parents=True, exist_ok=True)

    def write_counter(name: str, counter: Counter, key_name: str, top_n: int | None = None) -> pd.DataFrame:
        rows = counter.most_common(top_n) if top_n else counter.most_common()
        frame = pd.DataFrame(rows, columns=[key_name, "complaints"])
        frame.to_csv(output_dir / f"{name}.csv", index=False)
        return frame

    monthly = write_counter("monthly_complaints", monthly_counts, "date_received")
    monthly = monthly.sort_values("date_received").reset_index(drop=True)
    monthly.to_csv(output_dir / "monthly_complaints.csv", index=False)

    products = write_counter("product_complaints", counters["product"], "product")
    companies = write_counter("company_complaints", counters["company"], "company", 50)
    issues = write_counter("issue_complaints", counters["issue"], "issue", 50)
    sub_products = write_counter("sub_product_complaints", counters.get("sub_product", Counter()), "sub_product", 50)
    sub_issues = write_counter("sub_issue_complaints", counters.get("sub_issue", Counter()), "sub_issue", 50)
    states = write_counter("state_complaints", counters.get("state", Counter()), "state")
    channels = write_counter("submission_channel_complaints", counters.get("submitted_via", Counter()), "submitted_via")
    outcomes = write_counter("response_outcomes", counters["company_response_to_consumer"], "company_response_to_consumer")
    timely = write_counter("timely_response", counters.get("timely_response", Counter()), "timely_response")
    archives = write_counter("source_archive_complaints", counters.get("source_archive", Counter()), "source_archive")

    product_outcome_rows = [
        {"product": product, "outcome": outcome, "complaints": count}
        for (product, outcome), count in product_outcomes.items()
    ]
    pd.DataFrame(product_outcome_rows).to_csv(output_dir / "product_response_outcomes.csv", index=False)

    monthly_outcome_rows = [
        {"month": month, "outcome": outcome, "complaints": count}
        for (month, outcome), count in monthly_outcomes.items()
    ]
    pd.DataFrame(monthly_outcome_rows).to_csv(output_dir / "monthly_response_outcomes.csv", index=False)

    monetary = counters["company_response_to_consumer"].get("Closed with monetary relief", 0)
    total_outcomes = sum(counters["company_response_to_consumer"].values())
    monthly["prior_3_month_median"] = monthly["complaints"].rolling(3, min_periods=3).median().shift(1)
    monthly["ratio_to_prior_3_month_median"] = (
        monthly["complaints"] / monthly["prior_3_month_median"]
    )
    monthly["screening_flag"] = (
        (monthly["ratio_to_prior_3_month_median"] >= 1.5)
        | (monthly["ratio_to_prior_3_month_median"] <= 0.5)
    )
    monthly.to_csv(output_dir / "monthly_complaint_screening.csv", index=False)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "total_records": int(total),
        "monthly_periods": int(len(monthly)),
        "narrative_length": {
            "mean_characters": round(length_sum / total, 2) if total else None,
            "minimum_characters": length_min,
            "maximum_characters": length_max,
            "bins": dict(narrative_lengths),
        },
        "monetary_relief": {
            "count": int(monetary),
            "rate_pct": round(monetary / total_outcomes * 100, 4) if total_outcomes else 0.0,
        },
        "top_products": products.head(20).to_dict(orient="records"),
        "top_companies": companies.head(20).to_dict(orient="records"),
        "top_issues": issues.head(20).to_dict(orient="records"),
        "top_states": states.head(20).to_dict(orient="records"),
        "monthly_screening_flags": monthly.loc[
            monthly["screening_flag"].fillna(False),
            ["date_received", "complaints", "prior_3_month_median", "ratio_to_prior_3_month_median"]
        ].to_dict(orient="records"),
    }
    (output_dir / "eda_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Exploratory Data Analysis", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Records analysed: {total:,}",
        f"- Monthly periods observed: {len(monthly)}",
        f"- Mean narrative length: {payload['narrative_length']['mean_characters']} characters",
        f"- Monetary relief: {monetary:,} ({payload['monetary_relief']['rate_pct']:.2f}%)", "",
        "## Top products", "", "| Product | Complaints |", "|---|---:|",
    ]
    report += [f"| {r['product']} | {r['complaints']:,} |" for r in payload["top_products"]]
    report += ["", "## Top companies", "", "| Company | Complaints |", "|---|---:|"]
    report += [f"| {r['company']} | {r['complaints']:,} |" for r in payload["top_companies"]]
    report += ["", "## Top issues", "", "| Issue | Complaints |", "|---|---:|"]
    report += [f"| {r['issue']} | {r['complaints']:,} |" for r in payload["top_issues"]]
    report += ["", "## Monthly screening flags", "",
               "These flags compare a month's count with the median of the preceding three months. They are exploratory screens, not confirmed anomalies or evidence of underlying consumer incidence.", "",
               "| Month | Complaints | Prior 3-month median | Ratio |", "|---|---:|---:|---:|"]
    for row in payload["monthly_screening_flags"]:
        report.append(
            f"| {row['date_received']} | {row['complaints']:,} | "
            f"{row['prior_3_month_median']:.0f} | {row['ratio_to_prior_3_month_median']:.2f}x |"
        )
    report += [
        "", "## Files generated", "",
        "See the accompanying CSV tables for monthly counts, products, companies, issues, sub-products, sub-issues, states, channels, response outcomes, timeliness, archive contributions, and product/month response breakdowns.",
        "", "## Interpretation limitations", "",
        "- These are published CFPB complaint records with non-empty narratives, not a representative sample of all consumer experiences.",
        "- Counts are not population-adjusted rates and do not establish company misconduct or causation.",
        "- Large month-to-month changes require investigation of archive composition, publication lag, source changes, and reporting patterns before business interpretation.",
        "- Company response outcomes are post-submission outcomes and must not be used as features in a model intended to score complaints at submission.",
    ]
    (output_dir / "eda_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    config = load_config()
    d = config["data"]
    scan_eda(
        ROOT / d["parquet_dir"],
        ROOT / d["reports_dir"] / "eda",
        int(d.get("chunksize", 25_000)),
    )
    print("EDA complete: reports/eda/eda_report.md")


if __name__ == "__main__":
    main()
