# Advanced Financial Complaint Analytics

- Generated (UTC): 2026-11-25T06:58:50Z
- Records analysed: 1,842,530
- Distinct companies: 3,914
- Distinct products: 11
- Distinct issues: 89
- Monetary relief outcomes: 29,279 (1.59%)

## Top 10 companies

| Company | Complaints | Dataset share |
|---|---:|---:|
| EQUIFAX, INC. | 449,805 | 24.41% |
| TRANSUNION INTERMEDIATE HOLDINGS, INC. | 430,858 | 23.38% |
| Experian Information Solutions Inc. | 406,541 | 22.06% |
| Block, Inc. | 42,732 | 2.32% |
| CAPITAL ONE FINANCIAL CORPORATION | 26,624 | 1.45% |
| JPMORGAN CHASE & CO. | 21,055 | 1.14% |
| Early Warning Services, LLC | 18,619 | 1.01% |
| WELLS FARGO & COMPANY | 16,829 | 0.91% |
| CITIBANK, N.A. | 16,718 | 0.91% |
| BANK OF AMERICA, NATIONAL ASSOCIATION | 16,299 | 0.88% |

## Top product–issue combinations

| Product | Issue | Complaints |
|---|---|---:|
| Credit reporting or other personal consumer reports | Incorrect information on your report | 686,453 |
| Credit reporting or other personal consumer reports | Improper use of your report | 373,930 |
| Credit reporting or other personal consumer reports | Problem with a company's investigation into an existing problem | 255,988 |
| Debt collection | Attempts to collect debt not owed | 82,126 |
| Money transfer, virtual currency, or money service | Other transaction problem | 47,779 |
| Checking or savings account | Managing an account | 45,568 |
| Debt collection | Written notification about debt | 40,028 |
| Debt collection | False statements or representation | 23,095 |
| Credit card | Problem with a purchase shown on your statement | 21,386 |
| Mortgage | Trouble during payment process | 14,310 |
| Debt collection | Took or threatened to take negative or legal action | 14,270 |
| Checking or savings account | Problem caused by your funds being low | 11,851 |
| Money transfer, virtual currency, or money service | Fraud or scam | 11,431 |
| Student loan | Dealing with your lender or servicer | 11,369 |
| Checking or savings account | Closing an account | 10,960 |
| Checking or savings account | Problem with a lender or other company charging your account | 10,721 |
| Credit card | Other features, terms, or problems | 9,198 |
| Credit card | Fees or interest | 9,084 |
| Credit card | Getting a credit card | 8,958 |
| Debt collection | Communication tactics | 8,683 |

## Benchmarking interpretation

- Company counts are descriptive volumes, not company performance or misconduct rankings.
- `company_within_product_share.csv` compares a company's share within each product category, reducing product-mix distortion.
- Even within-product shares are not customer-normalized rates because account/customer exposure denominators are unavailable.
- Response outcomes are downstream outcomes and must not be used as features for a model scoring complaints at submission.
- Small groups should be suppressed or treated cautiously when making comparisons.
