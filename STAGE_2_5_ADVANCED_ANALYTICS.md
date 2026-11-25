# Stage 2.5 — Advanced Financial Complaint Analytics

## Prerequisites
- Stage 1 ingestion completed.
- Stage 2 Data Quality and EDA completed.
- Dependencies installed from `requirements.txt`.

## Run in this order

```bash
python -m src.advanced_analytics
python -m src.trend_investigation
python -m src.text_diagnostics
python -m unittest discover -s tests -v
```

All scripts read the configured Parquet dataset in batches. Outputs are written under `reports/advanced_analytics/`.

## Modules and decisions

### `src/analytics_common.py`
Centralizes config loading, Parquet opening, schema checks, UTC timestamps, and label cleanup so each analysis uses the same settings.

### `src/advanced_analytics.py`
Creates descriptive company, product, issue, state, response-outcome, and timely-response tables; product × issue and company × product × issue cross-tabs; within-product company shares; and Pareto concentration tables.

Company counts and shares are descriptive only. The dataset has no customer/account exposure denominator, so it cannot support company-normalized incidence or misconduct rankings.

### `src/trend_investigation.py`
Reconciles month counts with source archive composition and product composition. `source_archive` records which export contains a row; it is not a publication date and cannot establish publication lag.

The prior-three-month median is a screening heuristic, not a confirmed anomaly test.

### `src/text_diagnostics.py`
Measures narrative length and word-count distributions and detects exact duplicates after lowercasing, punctuation removal, and whitespace normalization. It uses a local SQLite SHA-256 index. Raw narratives and hashes are not exported. The SQLite index is local and must not be committed.

Exact repeated narratives are not automatically invalid: templates and copied wording may be legitimate. No records are deleted.

## Outputs

```text
reports/advanced_analytics/
├── advanced_analytics_report.md
├── advanced_analytics_summary.json
├── company_benchmark.csv
├── company_within_product_share.csv
├── company_product.csv
├── company_product_issue_top500.csv
├── product_benchmark.csv
├── issue_benchmark.csv
├── product_issue.csv
├── state_benchmark.csv
├── state_product.csv
├── response_outcomes.csv
├── timely_response.csv
├── product_response_outcomes.csv
├── company_response_outcomes_top500.csv
├── pareto_concentration.csv
├── trend_investigation_report.md
├── trend_investigation_summary.json
├── monthly_trend_investigation.csv
├── archive_contribution.csv
├── month_by_archive.csv
├── month_by_product.csv
├── text_diagnostics_report.md
├── text_diagnostics_summary.json
├── narrative_character_length_bands.csv
├── narrative_word_count_bands.csv
├── product_narrative_length_buckets.csv
└── narrative_hash_index.sqlite
```

## Interpretation and governance
- Counts are not rates of consumer harm or company performance.
- Complaint records are self-selected published records with narratives.
- Company response outcomes occur after submission; exclude them from submission-time predictive features.
- Do not infer publication lag from export-file membership alone.
- Do not delete duplicate narratives automatically.
- Do not commit raw CFPB archives, processed complaint-level Parquet, SQLite hash indexes, or sensitive complaint text to GitHub.
