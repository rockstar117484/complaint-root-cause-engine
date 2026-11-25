# Complaint Root-Cause Engine

**An end-to-end analytics and exploratory NLP project built on Consumer Financial Protection Bureau (CFPB) consumer complaint data.**

The project ingests historical CFPB complaint exports, validates and analyses the resulting dataset, benchmarks complaint patterns across products and companies, discovers exploratory narrative themes, and presents the findings in a Streamlit dashboard.

> **Interpretation note:** CFPB complaint records are self-selected published records. Counts and shares in this project describe the retained dataset; they are not population incidence rates, customer-normalized company performance measures, proof of misconduct, or causal findings. NLP clusters are exploratory text groupings, not verified root causes.

## Project highlights

- Processed **13 historical CFPB ZIP archives** through a chunked ingestion workflow.
- Retained **1,842,530 unique complaint records** with valid IDs, dates in the configured window, and non-empty narratives.
- Analysed the period **1 June 2024 to 31 May 2026**.
- Built data-quality checks, exploratory data analysis, company/product/issue benchmarking, response-outcome analysis, trend screening, and narrative duplicate diagnostics.
- Ran an exploratory NLP workflow on a deterministic sample of **30,000 narratives**, producing **20,000 TF-IDF features** and **6 MiniBatchKMeans clusters**.
- Built a Streamlit dashboard for executive overview, benchmarking, product/issue analysis, trends, NLP themes, and response outcomes.
- Verified the unit-test suite: **12 tests passed** in the user's reported local run.

## Analytical findings

### Dataset overview

| Measure | Result |
|---|---:|
| Retained complaints | 1,842,530 |
| Distinct companies | 3,914 |
| Product categories | 11 |
| Issue categories | 89 |
| Monetary-relief outcomes | 29,279 (1.59%) |

### Complaint concentration

The three largest company volumes in the retained dataset were Equifax (449,805; 24.41%), TransUnion (430,858; 23.38%), and Experian (406,541; 22.06%). These are dataset shares, not market shares or normalized performance rates.

The leading product–issue combination was **Credit reporting or other personal consumer reports → Incorrect information on your report**, with 686,453 complaints.

### Trend screening

A three-month rolling median screening identified unusually high volume in January 2025 (172,937; 2.17× the preceding three-month median) and low volumes in January 2026 (22,227; 0.29×) and February 2026 (12,124; 0.21×). These are investigation flags only. Source archive composition and publication timing must be examined before assigning an explanation. The source archive field identifies the export archive containing a record; it is not a publication timestamp.

### Narrative diagnostics

The normalized exact-text diagnostic identified 136,882 repeated-text groups and 876,579 rows beyond the first occurrence (47.57%). Repeated narratives may reflect templates, copied text, or recurring consumer wording. They were not automatically deleted, and raw narratives were not exported in diagnostic reports.

### Exploratory NLP

The 30,000-record sample was transformed using TF-IDF unigrams and bigrams (20,000 features) and grouped into six clusters with MiniBatchKMeans. The largest cluster contained 17,477 sample records (58.26%); the second contained 8,226 (27.42%). Top terms suggest substantial overlap around credit reporting and FCRA-related language, with smaller patterns involving identity theft/fraud, Cash App/transactions, and debt-verification language. These are preliminary interpretations requiring human review, not validated causal root causes. Sample shares are not full-dataset prevalence estimates.

## Repository structure

```text
complaint-root-cause-engine/
├── app/
│   ├── dashboard.py
│   └── dashboard_stage4.py
├── data/
│   ├── raw/                  # local CFPB ZIP archives; not committed
│   └── processed/            # local Parquet and SQLite files; not committed
├── reports/                  # generated outputs; generally not committed
├── src/
│   ├── ingest_archives.py
│   ├── data_quality.py
│   ├── eda.py
│   ├── visualizations.py
│   ├── analytics_common.py
│   ├── advanced_analytics.py
│   ├── trend_investigation.py
│   ├── text_diagnostics.py
│   └── stage3_nlp.py
├── tests/
├── config.yaml
├── requirements.txt
├── README.md
├── FINAL_BUSINESS_INSIGHTS.md
├── PROJECT_ARCHITECTURE.md
└── GITHUB_RELEASE_CHECKLIST.md
```

## Setup

Python 3.11 or newer is recommended. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\Activate.ps1  # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Place the original CFPB ZIP archives directly in `data/raw/`. Keep raw and processed data local; they are excluded from Git. Confirm the date window and paths in `config.yaml` before running ingestion.

## Reproduce the pipeline

Run commands from the repository root with the virtual environment activated.

### 1. Validate and ingest source archives

```bash
python -m src.ingest_archives --validate-only
python -m src.ingest_archives --run
```

### 2. Data quality, EDA and visualizations

```bash
python -m src.data_quality
python -m src.eda
python -m src.visualizations
```

### 3. Advanced analytics and diagnostics

```bash
python -m src.advanced_analytics
python -m src.trend_investigation
python -m src.text_diagnostics
```

### 4. Exploratory NLP

```bash
python -m src.stage3_nlp
```

### 5. Run tests

```bash
python -m unittest discover -s tests -v
```

### 6. Launch the dashboard

```bash
streamlit run app/dashboard_stage4.py
```

Stop the local Streamlit server with **Control+C** in the terminal.

## Main outputs

Generated outputs are written beneath `reports/` (see the stage guides for exact filenames):

- Data-quality and EDA reports and figures.
- `reports/advanced_analytics/`: company/product/issue benchmarks, within-product company shares, response outcomes, monthly trend screening, archive contribution, and narrative diagnostics.
- `reports/nlp/`: cluster profiles, cluster monthly trends, cluster/product mix, run summary, and NLP report.

The dashboard reads aggregate report files. It does not need raw complaint narratives for display.

## Methodology and design choices

- **Chunked ingestion:** processes large CSV members from ZIP archives without loading the entire source export into memory.
- **Schema normalization:** maps source headers to canonical field names.
- **Eligibility filters:** retains records with a complaint ID, valid date within the configured window, and non-empty narrative.
- **Deduplication:** uses complaint ID as the global key.
- **Parquet:** provides compressed columnar storage for downstream batch scans.
- **Aggregations:** reports complaint counts and shares; within-product shares reduce product-mix distortion but are still not customer/account normalized.
- **Trend screening:** compares monthly counts with the preceding three-month median; flags are heuristics, not statistical confirmation.
- **Text diagnostics:** hashes normalized narrative text for exact-repeat analysis; it does not establish invalidity or semantic similarity.
- **NLP:** TF-IDF unigrams/bigrams plus MiniBatchKMeans on a deterministic 30,000-record sample, with six requested clusters.
- **Privacy:** raw narrative text is not exported in NLP aggregate reports. Do not publish source archives, Parquet files, SQLite indexes, or raw narratives.

## Limitations

1. CFPB complaints are self-selected and do not represent all consumers or all financial experiences.
2. Complaint counts are not rates without customer, account, transaction, or market exposure denominators.
3. Company-level volume should not be interpreted as a misconduct or service-quality ranking.
4. Monthly changes may reflect publication coverage, archive composition, or reporting processes; the archive field is not a publication date.
5. NLP clusters are exploratory, sensitive to preprocessing/sample/model settings, and require human validation.
6. Company response and timely-response fields occur after complaint submission and must not be used as predictors in a model intended to score complaints at submission time.
7. This project does not currently claim a validated supervised prediction model or causal root-cause model.

## Documentation

- `STAGE_2_DATA_QUALITY_AND_EDA.md`
- `STAGE_2_5_ADVANCED_ANALYTICS.md`
- `STAGE_3_NLP_GUIDE.md`
- `STAGE_4_DASHBOARD_GUIDE.md`
- `FINAL_BUSINESS_INSIGHTS.md`
- `PROJECT_ARCHITECTURE.md`
- `GITHUB_RELEASE_CHECKLIST.md`

## Disclaimer

This is an independent analytical project using public CFPB complaint data. It is not affiliated with or endorsed by the CFPB or any financial institution. Findings are descriptive and exploratory and should not be used as standalone evidence of company misconduct or consumer-level risk.
