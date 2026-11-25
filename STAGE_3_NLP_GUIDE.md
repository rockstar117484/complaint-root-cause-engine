# Stage 3 — NLP and Complaint Intelligence

This stage is additive: it introduces `src/stage3_nlp.py` and `tests/test_stage3_nlp.py` without replacing the existing ingestion, EDA, or Stage 2.5 modules.

## Method

1. Read only the required fields from `data/processed/complaints_parquet`.
2. Select a reproducible sample across all Parquet batches using a deterministic hash of complaint IDs. This avoids selecting only the earliest rows in file order.
3. Clean whitespace in memory and create TF-IDF unigram/bigram features.
4. Fit MiniBatchKMeans to discover six exploratory text clusters.
5. Export cluster terms and aggregate product, issue, and monthly counts. Raw narratives and complaint IDs are not exported.

## Run

```bash
python -m pip install scikit-learn
python -m unittest discover -s tests -p 'test_stage3_nlp.py' -v
python -m src.stage3_nlp
```

Outputs are written to `reports/nlp/`:

- `cluster_profiles.csv`
- `cluster_monthly_trends.csv`
- `cluster_product_mix.csv`
- `nlp_run_summary.json`
- `nlp_report.md`

## Interpretation and limitations

- Clusters are exploratory groupings, not verified causal root causes.
- Sample shares are not full-population incidence rates.
- Top terms and metadata must be reviewed before naming a theme.
- The dataset does not provide customer/account exposure denominators.
- Complaint narratives can contain sensitive personal information; this stage does not export raw narratives.
