"""Synthetic tests for Stage 2.5 analytics.

These tests use a tiny synthetic Parquet dataset to validate aggregation,
archive reconciliation, and privacy-safe narrative diagnostics.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd

HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None
if HAS_PYARROW:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from src.advanced_analytics import run_advanced_analytics
    from src.trend_investigation import run_trend_investigation
    from src.text_diagnostics import run_text_diagnostics


@unittest.skipUnless(HAS_PYARROW, "Install project dependencies to run Parquet integration tests")
class Stage25Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.dataset_dir = self.base / "dataset"
        self.dataset_dir.mkdir()
        frame = pd.DataFrame({
            "complaint_id": ["1", "2", "3", "4"],
            "date_received": ["2024-06-01", "2024-06-02", "2024-07-01", "2024-07-03"],
            "source_archive": ["a.zip", "a.zip", "b.zip", "b.zip"],
            "product": ["Credit card", "Credit card", "Debt collection", "Debt collection"],
            "company": ["Bank A", "Bank A", "Agency B", "Agency B"],
            "issue": ["Fees", "Fees", "Debt not owed", "Debt not owed"],
            "state": ["CA", "CA", "TX", "TX"],
            "timely_response": ["Yes", "Yes", "No", "Yes"],
            "company_response_to_consumer": [
                "Closed with explanation", "Closed with monetary relief",
                "Closed with explanation", "Closed with non-monetary relief"
            ],
            "narrative": [
                "Duplicate test text.",
                "Duplicate test text!",
                "A different narrative.",
                "Another narrative."
            ],
        })
        pq.write_table(pa.Table.from_pandas(frame), self.dataset_dir / "part-0.parquet")
        self.frame = frame

    def tearDown(self):
        self.temp.cleanup()

    def test_advanced_analytics_counts_and_within_product(self):
        output = self.base / "advanced"
        result = run_advanced_analytics(self.dataset_dir, output, 2)
        self.assertEqual(result["records_analysed"], 4)

        table = pd.read_csv(output / "company_within_product_share.csv")
        self.assertTrue((table["share_within_product_pct"] == 100).all())

        company_product = pd.read_csv(output / "company_product.csv")
        bank_a = company_product[company_product["company"] == "Bank A"]
        self.assertEqual(int(bank_a["complaints"].iloc[0]), 2)

        product_issue = pd.read_csv(output / "product_issue.csv")
        fees = product_issue[product_issue["issue"] == "Fees"]
        self.assertEqual(int(fees["complaints"].iloc[0]), 2)

        # All one-way and grouped aggregations must reconcile to input rows.
        self.assertEqual(int(company_product["complaints"].sum()), 4)
        self.assertEqual(int(product_issue["complaints"].sum()), 4)

    def test_trend_archive_reconciliation(self):
        output = self.base / "trends"
        result = run_trend_investigation(self.dataset_dir, output, 2)
        self.assertEqual(result["months_observed"], 2)

        by_archive = pd.read_csv(output / "archive_contribution.csv")
        self.assertEqual(int(by_archive["complaints"].sum()), 4)

        by_month_archive = pd.read_csv(output / "month_by_archive.csv")
        self.assertEqual(int(by_month_archive["complaints"].sum()), 4)

        by_month_product = pd.read_csv(output / "month_by_product.csv")
        self.assertEqual(int(by_month_product["complaints"].sum()), 4)

    def test_text_exact_duplicate_detection_without_exporting_text(self):
        output = self.base / "text"
        result = run_text_diagnostics(self.dataset_dir, output, 2)
        self.assertEqual(result["exact_duplicate_rows_beyond_first"], 1)

        # Aggregate columns such as "narratives" are allowed. Raw text is not.
        csv_files = list(output.glob("*.csv"))
        self.assertTrue(csv_files, "Expected aggregate diagnostic CSV files")

        forbidden_texts = [
            "Duplicate test text.",
            "Duplicate test text!",
            "A different narrative.",
            "Another narrative.",
        ]
        for csv_file in csv_files:
            content = csv_file.read_text(encoding="utf-8")
            for raw_text in forbidden_texts:
                self.assertNotIn(
                    raw_text,
                    content,
                    f"Raw complaint text leaked into {csv_file.name}",
                )


if __name__ == "__main__":
    unittest.main()
