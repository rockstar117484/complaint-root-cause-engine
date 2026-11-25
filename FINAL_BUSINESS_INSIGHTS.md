# Final Business Insights and Recommendations

## Executive summary

This project analyses 1,842,530 CFPB complaint records with retained narratives from 13 historical export archives covering 1 June 2024 through 31 May 2026. The workflow combines data engineering, descriptive analytics, trend screening, exact-repeat text diagnostics, exploratory NLP, and a Streamlit dashboard.

The strongest descriptive signal is the concentration of published complaints in credit reporting. The NLP sample also produces several distinguishable text patterns, but the largest clusters overlap substantially in credit-reporting and FCRA-related language. The results are useful for prioritizing further investigation and operational review; they do not establish causal root causes or company misconduct.

## Evidence from the analysis

### 1. Dataset scale and coverage

- 13 historical ZIP archives were processed.
- 1,842,530 unique complaints were retained.
- 3,914 companies, 11 products, and 89 issues were represented.
- The configured analysis window was 1 June 2024–31 May 2026.

### 2. Credit reporting is the dominant complaint category

The three largest company complaint volumes were Equifax (449,805; 24.41% of the retained dataset), TransUnion (430,858; 23.38%), and Experian (406,541; 22.06%). These figures show concentration in this dataset, not market share, complaint incidence per customer, or a company quality ranking.

The leading product–issue pair was “Credit reporting or other personal consumer reports” and “Incorrect information on your report,” with 686,453 records. Other leading credit-reporting issues included improper use of a report (373,930) and problems with a company's investigation into an existing problem (255,988).

**Operational implication:** a financial institution or consumer-finance operations team could prioritize review workflows around dispute intake, accuracy of furnished information, investigation quality, and consistency of consumer communications. This is a prioritization hypothesis based on complaint volume, not proof that any specific company or process caused the complaints.

### 3. Monthly volume flags warrant coverage checks

The three-month median screen flagged January 2025 at 172,937 complaints (2.17× the preceding three-month median), January 2026 at 22,227 (0.29×), and February 2026 at 12,124 (0.21×).

**Operational implication:** before treating these as changes in consumer experience, compare month-by-archive and month-by-product contributions, confirm the source files' coverage, and obtain authoritative publication timing if available. The `source_archive` field is the export file containing a record, not the complaint publication date.

### 4. Repeated narratives are common and need context

The normalized exact-text diagnostic identified 136,882 repeated-text groups and 876,579 rows beyond the first occurrence (47.57%). Repetition may arise from templates, copied wording, legal boilerplate, or genuinely similar experiences. The project does not automatically delete repeated records.

**Operational implication:** use repeat patterns as a triage signal for further review, ideally segmented by product, issue, company, and archive. Do not treat repeated text alone as fraud, spam, or invalid complaints.

### 5. NLP surfaces overlapping complaint language

The deterministic NLP sample contained 30,000 narratives and generated 20,000 TF-IDF features before six MiniBatchKMeans clusters were created.

| Cluster | Sample count | Sample share | Preliminary term-based interpretation |
|---:|---:|---:|---|
| 0 | 17,477 | 58.26% | Credit reports, accounts, information, identity theft |
| 1 | 8,226 | 27.42% | Credit reporting, FCRA, inaccurate information |
| 5 | 1,545 | 5.15% | FCRA Section 1681 and consumer reporting language |
| 3 | 966 | 3.22% | Identity theft, fraud, hard inquiries |
| 2 | 938 | 3.13% | Cash App and transaction-related language |
| 4 | 848 | 2.83% | Debt verification and proof-related language |

Clusters 0, 1, 5, 3, and 4 are heavily associated with credit-reporting complaints. They may represent different wording styles or subthemes within an overlapping domain rather than five independent business root causes. Cluster 2 is smaller and has a stronger money-transfer/Cash App association. These interpretations are based on top terms and product mix and require human review.

## Recommended business actions

1. **Prioritize credit-report dispute operations:** review intake completeness, evidence capture, investigation handoffs, correction propagation, and consumer notification processes.
2. **Create issue-level monitoring:** track incorrect information, improper report use, and investigation-related complaints separately instead of relying only on overall complaint totals.
3. **Add coverage-aware trend monitoring:** flag sharp monthly changes, then reconcile archive contribution and product mix before escalating.
4. **Use NLP clusters as analyst triage:** inspect representative narratives in a controlled environment, assign human-reviewed theme labels, and measure inter-reviewer agreement before operational use.
5. **Review repeated-text patterns carefully:** distinguish standardized templates from potential data-quality or campaign effects; do not auto-delete duplicates.
6. **Keep outcome analysis separate from submission-time prediction:** response outcomes and timely-response fields are downstream of complaint submission and would create leakage if used as input features for a submission-time model.

## Suggested next analytical improvements

- Manually label a stratified sample of narratives and evaluate cluster coherence and stability.
- Compare alternative cluster counts and preprocessing choices using stability checks and analyst review.
- Add account/customer denominators if legitimately available to support normalized rates.
- Investigate archive-level and product-level monthly shifts with confirmed source publication metadata.
- If building a supervised model, define a precise prediction target and prediction timestamp first; split chronologically and exclude post-submission variables.

## Limitations and responsible interpretation

- CFPB complaint data is self-selected and does not represent all consumer experiences.
- Counts and shares describe retained published records, not population incidence.
- Company volume comparisons lack customer/account exposure denominators.
- Trend flags are heuristic screening signals, not statistically confirmed anomalies.
- Repeated narratives are not automatically invalid.
- NLP clusters are exploratory and not validated causal root causes.
- The project does not claim a validated predictive model.

## Conclusion

The Complaint Root-Cause Engine provides a reproducible workflow for transforming large public complaint exports into structured descriptive evidence and exploratory narrative themes. Its practical value is in helping analysts decide where to investigate next, not in automatically assigning blame or claiming causal explanations.
