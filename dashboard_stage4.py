"""Additive Stage 4 dashboard. Does not modify the existing dashboard.py."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
ADV = ROOT / "reports" / "advanced_analytics"
NLP = ROOT / "reports" / "nlp"

st.set_page_config(page_title="Complaint Root-Cause Engine", page_icon="📊", layout="wide")
st.title("Consumer Financial Complaint Intelligence")
st.caption("CFPB published complaint records | Descriptive analytics + exploratory NLP")

@st.cache_data(show_spinner=False)
def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()

@st.cache_data(show_spinner=False)
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

summary = read_json(ADV / "advanced_analytics_summary.json")
nlp_summary = read_json(NLP / "nlp_run_summary.json")
companies = read_csv(ADV / "company_benchmark.csv")
products = read_csv(ADV / "product_benchmark.csv")
issues = read_csv(ADV / "issue_benchmark.csv")
product_issue = read_csv(ADV / "product_issue.csv")
within_product = read_csv(ADV / "company_within_product_share.csv")
responses = read_csv(ADV / "response_outcomes.csv")
timely = read_csv(ADV / "timely_response.csv")
monthly = read_csv(ADV / "monthly_trend_investigation.csv")
month_product = read_csv(ADV / "month_by_product.csv")
profiles = read_csv(NLP / "cluster_profiles.csv")
cluster_monthly = read_csv(NLP / "cluster_monthly_trends.csv")
cluster_product = read_csv(NLP / "cluster_product_mix.csv")

# Executive overview
st.header("1. Executive overview")
if summary:
    a, b, c, d = st.columns(4)
    a.metric("Narrative-retained complaints", f"{summary.get('records_analysed', 0):,}")
    b.metric("Distinct companies", f"{summary.get('distinct_companies', 0):,}")
    c.metric("Products", f"{summary.get('distinct_products', 0):,}")
    d.metric("Issues", f"{summary.get('distinct_issues', 0):,}")
    st.caption(f"Monetary relief outcomes: {summary.get('monetary_relief_count', 0):,} ({summary.get('monetary_relief_share_pct', 0):.2f}%)")
else:
    st.warning("Advanced analytics summary not found. Run: python -m src.advanced_analytics")

left, right = st.columns(2)
with left:
    st.subheader("Top products")
    if not products.empty and {'product','complaints'}.issubset(products.columns):
        chart = products.head(10).sort_values('complaints')
        st.bar_chart(chart.set_index('product')['complaints'])
    else:
        st.info("product_benchmark.csv not found.")
with right:
    st.subheader("Top companies by complaint volume")
    if not companies.empty and {'company','complaints'}.issubset(companies.columns):
        chart = companies.head(10).sort_values('complaints')
        st.bar_chart(chart.set_index('company')['complaints'])
    else:
        st.info("company_benchmark.csv not found.")

# Company benchmarking
st.header("2. Company benchmarking")
st.caption("Volumes and within-product shares are descriptive; they are not customer-normalized performance or misconduct rates.")
if not companies.empty:
    st.dataframe(companies.head(25), use_container_width=True, hide_index=True)
if not within_product.empty:
    choices = sorted(within_product['product'].dropna().astype(str).unique()) if 'product' in within_product else []
    if choices:
        selected_product = st.selectbox("Compare companies within product", choices)
        view = within_product[within_product['product'].astype(str) == selected_product].sort_values('share_within_product_pct', ascending=False).head(15)
        st.dataframe(view, use_container_width=True, hide_index=True)

# Product / issue
st.header("3. Product and issue analysis")
if not product_issue.empty:
    st.dataframe(product_issue.head(30), use_container_width=True, hide_index=True)
else:
    st.info("product_issue.csv not found.")

# Trends
st.header("4. Trend analysis")
if not monthly.empty and {'month','complaints'}.issubset(monthly.columns):
    monthly = monthly.sort_values('month')
    st.line_chart(monthly.set_index('month')['complaints'])
    if 'screening_flag' in monthly:
        flags = monthly[monthly['screening_flag'].astype(str).str.lower().isin(['true','1'])]
        if not flags.empty:
            st.warning("Monthly screening signals require investigation; they are not confirmed anomalies.")
            st.dataframe(flags, use_container_width=True, hide_index=True)
else:
    st.info("monthly_trend_investigation.csv not found. Run: python -m src.trend_investigation")
if not month_product.empty and {'month','product','complaints'}.issubset(month_product.columns):
    products_for_trend = sorted(month_product['product'].dropna().astype(str).unique())
    if products_for_trend:
        selected = st.selectbox("Inspect monthly trend by product", products_for_trend)
        pv = month_product[month_product['product'].astype(str) == selected].sort_values('month')
        st.line_chart(pv.set_index('month')['complaints'])

# NLP
st.header("5. NLP complaint intelligence")
if nlp_summary and not profiles.empty:
    x, y, z = st.columns(3)
    x.metric("Narratives sampled", f"{nlp_summary.get('sample_records', 0):,}")
    y.metric("TF-IDF features", f"{nlp_summary.get('tfidf_features', 0):,}")
    z.metric("Clusters", nlp_summary.get('clusters_created', 0))
    st.dataframe(profiles, use_container_width=True, hide_index=True)
    if not cluster_monthly.empty and {'month','cluster_id','sample_complaints'}.issubset(cluster_monthly.columns):
        pv = cluster_monthly.pivot_table(index='month', columns='cluster_id', values='sample_complaints', aggfunc='sum', fill_value=0).sort_index()
        st.subheader("Cluster volume over time (NLP sample)")
        st.line_chart(pv)
    if not cluster_product.empty:
        st.subheader("Cluster and product composition")
        st.dataframe(cluster_product.sort_values('sample_complaints', ascending=False).head(40), use_container_width=True, hide_index=True)
else:
    st.info("NLP outputs not found. Run: python -m src.stage3_nlp")
st.caption("Cluster groupings are exploratory text patterns, not validated causal root causes. Sample shares are not population complaint rates.")

# Outcomes
st.header("6. Company response analysis")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Response outcomes")
    if not responses.empty:
        st.dataframe(responses, use_container_width=True, hide_index=True)
    else:
        st.info("response_outcomes.csv not found.")
with col2:
    st.subheader("Timely response")
    if not timely.empty:
        st.dataframe(timely, use_container_width=True, hide_index=True)
    else:
        st.info("timely_response.csv not found.")

st.divider()
st.caption("Data interpretation: this dashboard describes published CFPB complaint records with retained narratives. It does not estimate population incidence, prove company misconduct, or establish causality. Response outcomes occur after complaint submission and should not be used as submission-time prediction features.")
