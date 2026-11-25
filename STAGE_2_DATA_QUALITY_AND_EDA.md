# Stage 2 — Data Quality & EDA

## Install updated dependencies

```bash
pip install -r requirements.txt
```

## Run the data-quality audit

```bash
python -m src.data_quality
```

This scans the Parquet dataset in batches. It checks schema, nulls and blank strings, Complaint ID uniqueness (using a temporary SQLite index), date coverage, missing months, outcome labels, narrative lengths, top products/states, and source archive contribution.

Outputs:
- `reports/data_quality_report.md`
- `reports/data_quality_report.json`
- `reports/data_quality_ids.sqlite` (temporary audit index; ignored by Git through data/report policy if placed in reports, see .gitignore update)

## Run EDA

```bash
python -m src.eda
```

Outputs are in `reports/eda/`:
- monthly complaint counts and rolling screening flags;
- top products, companies, issues, sub-products and sub-issues;
- state, submission-channel and response-outcome counts;
- response outcome breakdown by product and month;
- narrative length summary;
- JSON and Markdown reports.

## Generate charts

```bash
python -m src.visualizations
```

Charts are written to `reports/eda/figures/`.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Important interpretation safeguards

- The dataset already contains only complaints with non-empty narratives. Its null narrative count should be zero; this audit cannot estimate narrative availability among the original 10.59 million source rows.
- A missing optional field is not necessarily a defective row.
- Monthly screening flags use the previous three months' median and are exploratory only. Investigate publication timing and source archive composition before interpreting them as risk signals.
- Complaint counts are not exposure-adjusted incidence rates.
- Company response outcomes are post-submission fields and are not permitted as predictors for a submission-time prediction model.
