"""Unit tests for schema mapping and basic record filters."""
import unittest
import pandas as pd
from src.ingest_archives import normalise_header, resolve_columns, canonicalise_chunk


class IngestionTests(unittest.TestCase):
    def test_header_normalisation(self):
        self.assertEqual(normalise_header("Timely response?"), "timelyresponse")
        self.assertEqual(normalise_header("Sub-product"), "subproduct")

    def test_alias_mapping(self):
        aliases = {
            "complaint_id": ["Complaint ID", "complaint_id"],
            "narrative": ["Consumer complaint narrative", "narrative"],
        }
        result = resolve_columns(["Complaint ID", "Consumer complaint narrative"], aliases)
        self.assertEqual(result["complaint_id"], "Complaint ID")
        self.assertEqual(result["narrative"], "Consumer complaint narrative")

    def test_date_and_narrative_filters(self):
        frame = pd.DataFrame({
            "Complaint ID": ["1", "2", "3"],
            "Date received": ["2024-06-01", "2024-05-31", "2024-07-01"],
            "Product": ["Credit card"] * 3,
            "Consumer complaint narrative": ["Text", "Outside", "  "],
            "Company response to consumer": ["Closed with explanation"] * 3,
        })
        mapping = {
            "complaint_id": "Complaint ID", "date_received": "Date received",
            "product": "Product", "sub_product": None, "issue": None, "sub_issue": None,
            "narrative": "Consumer complaint narrative", "company_public_response": None,
            "company": None, "state": None, "zip_code": None, "tags": None,
            "submitted_via": None, "date_sent_to_company": None,
            "company_response_to_consumer": "Company response to consumer",
            "timely_response": None,
        }
        result, stats = canonicalise_chunk(
            frame, mapping, pd.Timestamp("2024-06-01"), pd.Timestamp("2026-05-31")
        )
        self.assertEqual(result["complaint_id"].tolist(), ["1"])
        self.assertEqual(stats["outside_date_window"], 1)
        self.assertEqual(stats["missing_narrative"], 1)


if __name__ == "__main__":
    unittest.main()
