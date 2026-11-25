# Data Source Notes

## Source

CFPB Consumer Complaint Database historical exports:
https://www.consumerfinance.gov/data-research/consumer-complaints/

The project uses the user's 13 downloaded historical ZIP exports. The configured analytical window is June 1, 2024 through May 31, 2026. The raw archives include additional April–May 2024 records, which the ingestion filter excludes.

## Required fields

Complaint ID, Date received, Product, Consumer complaint narrative, Company response to consumer.

Other fields are retained when available: Sub-product, Issue, Sub-issue, Company public response, Company, State, ZIP code, Tags, Submitted via, Date sent to company, Timely response?

## Provenance checklist

Record the archive filenames, download date, source page, headers, observed date coverage, duplicate ID count and narrative coverage.

## Limitations

CFPB complaint records are self-selected, not a statistical sample of all consumer experiences. Narratives are published only when consumers consent to publication. Trends in published records may reflect reporting and publication patterns as well as underlying consumer problems.
