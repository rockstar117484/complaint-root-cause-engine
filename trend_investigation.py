"""Investigate monthly counts and source-archive composition.

Run:
    python -m src.trend_investigation

Archive composition is a diagnostic, not a publication-date field. This module
cannot prove publication lag or explain a change in consumer incidence.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import pandas as pd

from src.analytics_common import (
    clean_label, configured_dataset, open_dataset, require_columns, utc_now, write_csv
)


def run_trend_investigation(dataset_path: Path, output_dir: Path, batch_size: int = 25_000) -> dict:
    dataset = open_dataset(dataset_path)
    require_columns(dataset, ["date_received", "source_archive", "product"])
    monthly = Counter()
    month_archive = Counter()
    archive_total = Counter()
    month_product = Counter()
    total = 0

    for batch in dataset.scanner(
        columns=["date_received", "source_archive", "product"], batch_size=batch_size
    ).to_batches():
        frame = batch.to_pandas()
        total += len(frame)
        dates = pd.to_datetime(frame["date_received"], errors="coerce")
        month = dates.dt.to_period("M").astype(str)
        archive = clean_label(frame["source_archive"])
        product = clean_label(frame["product"])
        monthly.update(month.value_counts().to_dict())
        archive_total.update(archive.value_counts().to_dict())
        month_archive.update({
            (m, a): int(n) for (m, a), n in
            frame.assign(_month=month, _archive=archive)
                 .groupby(["_month", "_archive"], dropna=False).size().items()
        })
        month_product.update({
            (m, p): int(n) for (m, p), n in
            frame.assign(_month=month, _product=product)
                 .groupby(["_month", "_product"], dropna=False).size().items()
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    months = sorted(monthly)
    monthly_rows = []
    for index, month in enumerate(months):
        prior = [monthly[m] for m in months[max(0, index - 3):index]]
        median = float(pd.Series(prior).median()) if len(prior) == 3 else None
        count = int(monthly[month])
        ratio = count / median if median else None
        monthly_rows.append({
            "month": month,
            "complaints": count,
            "prior_3_month_median": median,
            "ratio_to_prior_3_month_median": round(ratio, 4) if ratio is not None else None,
            "screening_flag": bool(ratio is not None and (ratio >= 1.5 or ratio <= 0.5)),
        })
    write_csv(monthly_rows, output_dir / "monthly_trend_investigation.csv",
              ["month", "complaints", "prior_3_month_median", "ratio_to_prior_3_month_median", "screening_flag"])

    archive_rows = [
        {"source_archive": archive, "complaints": int(count),
         "share_pct": round(count / total * 100, 4)}
        for archive, count in archive_total.most_common()
    ]
    write_csv(archive_rows, output_dir / "archive_contribution.csv",
              ["source_archive", "complaints", "share_pct"])

    month_archive_rows = []
    month_archive_totals = Counter()
    for (month, archive), count in month_archive.items():
        month_archive_totals[month] += count
        month_archive_rows.append({
            "month": month, "source_archive": archive, "complaints": int(count),
            "share_of_month_pct": 0.0,
        })
    for row in month_archive_rows:
        row["share_of_month_pct"] = round(row["complaints"] / month_archive_totals[row["month"]] * 100, 4)
    write_csv(month_archive_rows, output_dir / "month_by_archive.csv",
              ["month", "source_archive", "complaints", "share_of_month_pct"])

    month_product_rows = [
        {"month": month, "product": product, "complaints": int(count)}
        for (month, product), count in month_product.items()
    ]
    write_csv(month_product_rows, output_dir / "month_by_product.csv",
              ["month", "product", "complaints"])

    flags = [row for row in monthly_rows if row["screening_flag"]]
    payload = {
        "generated_at_utc": utc_now(),
        "records_analysed": total,
        "months_observed": len(months),
        "archives_observed": len(archive_total),
        "screening_flags": flags,
        "limitations": [
            "source_archive identifies the export file containing a record, not its publication date",
            "archive composition cannot by itself establish publication lag or explain changes in consumer incidence",
            "monthly counts are counts in the narrative-retained dataset, not population-adjusted rates",
            "three-month median flags are screening signals, not statistically confirmed anomalies",
        ],
    }
    (output_dir / "trend_investigation_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report = [
        "# Trend and Source-Archive Investigation", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Records analysed: {total:,}",
        f"- Months observed: {len(months)}",
        f"- Source archives observed: {len(archive_total)}", "",
        "## Monthly screening signals", "",
        "| Month | Complaints | Prior 3-month median | Ratio |", "|---|---:|---:|---:|",
    ]
    for row in flags:
        report.append(
            f"| {row['month']} | {row['complaints']:,} | "
            f"{row['prior_3_month_median']:,.0f} | {row['ratio_to_prior_3_month_median']:.2f}x |"
        )
    report += ["", "## Interpretation safeguards", ""] + [f"- {item}" for item in payload["limitations"]]
    report += [
        "", "Inspect `month_by_archive.csv` to see which source archives contribute to each month.",
        "Inspect `month_by_product.csv` to test whether a monthly shift is concentrated in one product.",
        "Do not label a flag as a confirmed anomaly until source coverage and publication timing have been independently verified.",
    ]
    (output_dir / "trend_investigation_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    dataset_path, output_dir, batch_size = configured_dataset()
    result = run_trend_investigation(dataset_path, output_dir, batch_size)
    print(f"Trend investigation complete: {output_dir / 'trend_investigation_report.md'}")
    print(f"Screening flags: {len(result['screening_flags'])}")


if __name__ == "__main__":
    main()
