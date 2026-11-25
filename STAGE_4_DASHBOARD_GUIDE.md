# Stage 4 — Streamlit Business Intelligence Dashboard

This is an additive dashboard entry point. It intentionally does not overwrite `app/dashboard.py`.

## Run

From the project root, with the project virtual environment active:

```bash
python -m pip install streamlit
streamlit run app/dashboard_stage4.py
```

## Required generated inputs

- `reports/advanced_analytics/advanced_analytics_summary.json`
- `reports/advanced_analytics/company_benchmark.csv`
- `reports/advanced_analytics/product_benchmark.csv`
- `reports/advanced_analytics/issue_benchmark.csv`
- `reports/advanced_analytics/product_issue.csv`
- `reports/advanced_analytics/company_within_product_share.csv`
- `reports/advanced_analytics/response_outcomes.csv`
- `reports/advanced_analytics/timely_response.csv`
- `reports/advanced_analytics/monthly_trend_investigation.csv`
- `reports/advanced_analytics/month_by_product.csv`
- `reports/nlp/nlp_run_summary.json`
- `reports/nlp/cluster_profiles.csv`
- `reports/nlp/cluster_monthly_trends.csv`
- `reports/nlp/cluster_product_mix.csv`

If any Stage 2.5 output is missing, rerun the corresponding existing module:

```bash
python -m src.advanced_analytics
python -m src.trend_investigation
python -m src.stage3_nlp
```

The dashboard reads aggregate outputs only and does not load or display raw narratives. Complaint counts are descriptive records, not population rates or company misconduct rankings. NLP clusters are exploratory and require human review.
