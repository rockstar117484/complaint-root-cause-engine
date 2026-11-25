# Decisions and Issues Log

Record only problems actually observed during execution.

## Decisions

| ID | Decision | Reason |
|---|---|---|
| D-001 | Initial analysis window: June 2024–May 2026 | 24 monthly periods for historical trend analysis |
| D-002 | Stream ZIP CSVs in 25,000-row chunks | Control memory and avoid extracting all source files |
| D-003 | SQLite primary key on Complaint ID | Disk-backed global deduplication |
| D-004 | Write Parquet parts | Efficient columnar downstream processing |
| D-005 | Require non-empty narratives | NLP clustering requires actual text |
| D-006 | Keep company response as outcome only | Prevent post-filing label leakage |

## Issues encountered

No actual archive-ingestion failures have been observed yet.

For each real issue, record:
- Expected
- Observed
- Root cause
- Resolution
- Validation after fix
- What I learned
