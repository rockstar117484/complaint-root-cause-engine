"""Company, product, issue, outcome and geographic benchmarking.

Run:
    python -m src.advanced_analytics

All measures are complaint counts/shares within this published narrative dataset.
They are not customer-normalized incidence rates or company misconduct rankings.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import pandas as pd

from src.analytics_common import (
    clean_label, configured_dataset, open_dataset, require_columns, utc_now, write_csv
)


def run_advanced_analytics(dataset_path: Path, output_dir: Path, batch_size: int = 25_000) -> dict:
    dataset = open_dataset(dataset_path)
    required = [
        "company", "product", "issue", "company_response_to_consumer",
        "state", "timely_response",
    ]
    require_columns(dataset, required)

    columns = required
    counters = {
        "company": Counter(),
        "product": Counter(),
        "issue": Counter(),
        "state": Counter(),
        "outcome": Counter(),
        "timely": Counter(),
        "company_product": Counter(),
        "product_issue": Counter(),
        "company_product_issue": Counter(),
        "product_outcome": Counter(),
        "company_outcome": Counter(),
        "state_product": Counter(),
    }
    total = 0

    for batch in dataset.scanner(columns=columns, batch_size=batch_size).to_batches():
        frame = batch.to_pandas()
        total += len(frame)
        company = clean_label(frame["company"])
        product = clean_label(frame["product"])
        issue = clean_label(frame["issue"])
        state = clean_label(frame["state"])
        outcome = clean_label(frame["company_response_to_consumer"])
        timely = clean_label(frame["timely_response"])

        counters["company"].update(company.value_counts().to_dict())
        counters["product"].update(product.value_counts().to_dict())
        counters["issue"].update(issue.value_counts().to_dict())
        counters["state"].update(state.value_counts().to_dict())
        counters["outcome"].update(outcome.value_counts().to_dict())
        counters["timely"].update(timely.value_counts().to_dict())

        counters["company_product"].update({
            (c, p): int(n) for (c, p), n in
            frame.assign(_company=company, _product=product)
                 .groupby(["_company", "_product"], dropna=False).size().items()
        })
        counters["product_issue"].update({
            (p, i): int(n) for (p, i), n in
            frame.assign(_product=product, _issue=issue)
                 .groupby(["_product", "_issue"], dropna=False).size().items()
        })
        counters["company_product_issue"].update({
            (c, p, i): int(n) for (c, p, i), n in
            frame.assign(_company=company, _product=product, _issue=issue)
                 .groupby(["_company", "_product", "_issue"], dropna=False).size().items()
        })
        counters["product_outcome"].update({
            (p, o): int(n) for (p, o), n in
            frame.assign(_product=product, _outcome=outcome)
                 .groupby(["_product", "_outcome"], dropna=False).size().items()
        })
        counters["company_outcome"].update({
            (c, o): int(n) for (c, o), n in
            frame.assign(_company=company, _outcome=outcome)
                 .groupby(["_company", "_outcome"], dropna=False).size().items()
        })
        counters["state_product"].update({
            (s, p): int(n) for (s, p), n in
            frame.assign(_state=state, _product=product)
                 .groupby(["_state", "_product"], dropna=False).size().items()
        })

    output_dir.mkdir(parents=True, exist_ok=True)

    def ranked(counter: Counter, key_names: list[str], top_n: int | None = None) -> list[dict]:
        rows = []
        items = counter.most_common(top_n)
        for rank, (key, count) in enumerate(items, start=1):
            values = key if isinstance(key, tuple) else (key,)
            row = {name: value for name, value in zip(key_names, values)}
            row.update({"complaints": int(count), "share_pct": round(count / total * 100, 4), "rank": rank})
            rows.append(row)
        return rows

    company_rows = ranked(counters["company"], ["company"])
    product_rows = ranked(counters["product"], ["product"])
    issue_rows = ranked(counters["issue"], ["issue"])
    state_rows = ranked(counters["state"], ["state"])
    outcome_rows = ranked(counters["outcome"], ["outcome"])
    timely_rows = ranked(counters["timely"], ["timely_response"])
    company_product_rows = ranked(counters["company_product"], ["company", "product"])
    product_issue_rows = ranked(counters["product_issue"], ["product", "issue"])
    company_product_issue_rows = ranked(counters["company_product_issue"], ["company", "product", "issue"], 500)
    product_outcome_rows = ranked(counters["product_outcome"], ["product", "outcome"])
    company_outcome_rows = ranked(counters["company_outcome"], ["company", "outcome"], 500)
    state_product_rows = ranked(counters["state_product"], ["state", "product"])

    # Within-product company share is more meaningful than comparing raw company totals.
    product_totals = Counter()
    for (company, product), count in counters["company_product"].items():
        product_totals[product] += count
    within_product_rows = []
    for (company, product), count in counters["company_product"].items():
        within_product_rows.append({
            "company": company,
            "product": product,
            "complaints": int(count),
            "product_total": int(product_totals[product]),
            "share_within_product_pct": round(count / product_totals[product] * 100, 4),
        })
    within_product_rows.sort(key=lambda row: (row["product"], -row["complaints"]))

    tables = {
        "company_benchmark": (company_rows, ["company", "complaints", "share_pct", "rank"]),
        "product_benchmark": (product_rows, ["product", "complaints", "share_pct", "rank"]),
        "issue_benchmark": (issue_rows, ["issue", "complaints", "share_pct", "rank"]),
        "state_benchmark": (state_rows, ["state", "complaints", "share_pct", "rank"]),
        "response_outcomes": (outcome_rows, ["outcome", "complaints", "share_pct", "rank"]),
        "timely_response": (timely_rows, ["timely_response", "complaints", "share_pct", "rank"]),
        "company_product": (company_product_rows, ["company", "product", "complaints", "share_pct", "rank"]),
        "company_within_product_share": (within_product_rows, ["company", "product", "complaints", "product_total", "share_within_product_pct"]),
        "product_issue": (product_issue_rows, ["product", "issue", "complaints", "share_pct", "rank"]),
        "company_product_issue_top500": (company_product_issue_rows, ["company", "product", "issue", "complaints", "share_pct", "rank"]),
        "product_response_outcomes": (product_outcome_rows, ["product", "outcome", "complaints", "share_pct", "rank"]),
        "company_response_outcomes_top500": (company_outcome_rows, ["company", "outcome", "complaints", "share_pct", "rank"]),
        "state_product": (state_product_rows, ["state", "product", "complaints", "share_pct", "rank"]),
    }
    for name, (rows, cols) in tables.items():
        write_csv(rows, output_dir / f"{name}.csv", cols)

    # Pareto concentration across products and companies.
    pareto = []
    for dimension in ("company", "product", "issue"):
        ordered = counters[dimension].most_common()
        cumulative = 0
        for rank, (label, count) in enumerate(ordered, start=1):
            cumulative += count
            pareto.append({
                "dimension": dimension, "rank": rank, "label": label,
                "complaints": int(count), "cumulative_share_pct": round(cumulative / total * 100, 4)
            })
    write_csv(pareto, output_dir / "pareto_concentration.csv",
              ["dimension", "rank", "label", "complaints", "cumulative_share_pct"])

    monetary = counters["outcome"].get("Closed with monetary relief", 0)
    payload = {
        "generated_at_utc": utc_now(),
        "records_analysed": total,
        "distinct_companies": len(counters["company"]),
        "distinct_products": len(counters["product"]),
        "distinct_issues": len(counters["issue"]),
        "monetary_relief_count": monetary,
        "monetary_relief_share_pct": round(monetary / total * 100, 4) if total else 0.0,
        "top_10_companies": company_rows[:10],
        "top_10_products": product_rows[:10],
        "top_10_issues": issue_rows[:10],
        "methodology_note": (
            "Counts and shares describe this published CFPB narrative dataset. "
            "No customer/account denominator is available; do not interpret as incidence "
            "rates, company quality scores, or evidence of misconduct."
        ),
    }
    (output_dir / "advanced_analytics_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = [
        "# Advanced Financial Complaint Analytics", "",
        f"- Generated (UTC): {payload['generated_at_utc']}",
        f"- Records analysed: {total:,}",
        f"- Distinct companies: {payload['distinct_companies']:,}",
        f"- Distinct products: {payload['distinct_products']:,}",
        f"- Distinct issues: {payload['distinct_issues']:,}",
        f"- Monetary relief outcomes: {monetary:,} ({payload['monetary_relief_share_pct']:.2f}%)", "",
        "## Top 10 companies", "", "| Company | Complaints | Dataset share |", "|---|---:|---:|",
    ]
    report += [f"| {r['company']} | {r['complaints']:,} | {r['share_pct']:.2f}% |" for r in company_rows[:10]]
    report += ["", "## Top product–issue combinations", "", "| Product | Issue | Complaints |", "|---|---|---:|"]
    report += [f"| {r['product']} | {r['issue']} | {r['complaints']:,} |" for r in product_issue_rows[:20]]
    report += [
        "", "## Benchmarking interpretation", "",
        "- Company counts are descriptive volumes, not company performance or misconduct rankings.",
        "- `company_within_product_share.csv` compares a company's share within each product category, reducing product-mix distortion.",
        "- Even within-product shares are not customer-normalized rates because account/customer exposure denominators are unavailable.",
        "- Response outcomes are downstream outcomes and must not be used as features for a model scoring complaints at submission.",
        "- Small groups should be suppressed or treated cautiously when making comparisons.",
    ]
    (output_dir / "advanced_analytics_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    dataset_path, output_dir, batch_size = configured_dataset()
    result = run_advanced_analytics(dataset_path, output_dir, batch_size)
    print(f"Advanced analytics complete: {output_dir / 'advanced_analytics_report.md'}")
    print(f"Records analysed: {result['records_analysed']:,}")


if __name__ == "__main__":
    main()
