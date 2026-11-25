"""Tests for data-quality schema validation."""
import importlib.util
import unittest
from pathlib import Path
import tempfile
import pandas as pd

HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None

if HAS_PYARROW:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from src.data_quality import get_dataset, REQUIRED_COLUMNS


@unittest.skipUnless(HAS_PYARROW, "pyarrow is installed from requirements.txt for Parquet tests")
class DataQualityTests(unittest.TestCase):
    def test_required_columns_are_declared(self):
        self.assertIn("complaint_id", REQUIRED_COLUMNS)
        self.assertIn("narrative", REQUIRED_COLUMNS)

    def test_dataset_schema_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.parquet"
            frame = pd.DataFrame({
                "complaint_id": ["1"],
                "date_received": ["2024-06-01"],
                "product": ["Credit card"],
                "narrative": ["A sample complaint"],
                "company_response_to_consumer": ["Closed with explanation"],
            })
            pq.write_table(pa.Table.from_pandas(frame), path)
            dataset = get_dataset(path)
            self.assertEqual(set(dataset.schema.names), set(frame.columns))

    def test_missing_required_column_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.parquet"
            frame = pd.DataFrame({
                "complaint_id": ["1"],
                "date_received": ["2024-06-01"],
                "product": ["Credit card"],
                "narrative": ["A sample complaint"],
            })
            pq.write_table(pa.Table.from_pandas(frame), path)
            with self.assertRaises(ValueError):
                get_dataset(path)


if __name__ == "__main__":
    unittest.main()
