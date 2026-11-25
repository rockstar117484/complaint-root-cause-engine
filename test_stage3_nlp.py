import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans

from src.stage3_nlp import clean_narrative, build_features, create_cluster_profiles


class Stage3NLPTests(unittest.TestCase):
    def test_clean_narrative_handles_null_and_whitespace(self):
        self.assertEqual(clean_narrative(None), "")
        self.assertEqual(clean_narrative("  payment   was   missing\nagain "), "payment was missing again")

    def test_tfidf_builds_unigram_and_bigram_features(self):
        texts = pd.Series([
            "credit card payment missing from account statement",
            "credit card payment posted late to account",
            "bank transfer payment missing from account",
            "credit card statement has incorrect payment fee",
            "bank transfer was delayed and payment missing",
            "credit card payment fee charged twice",
        ] * 3)
        vectorizer, matrix = build_features(texts)
        self.assertEqual(matrix.shape[0], len(texts))
        self.assertGreater(matrix.shape[1], 0)
        self.assertIn("credit card", vectorizer.get_feature_names_out())

    def test_cluster_profile_contains_aggregates_not_raw_narrative(self):
        sample = pd.DataFrame({
            "narrative": ["private raw complaint narrative one", "private raw complaint narrative two",
                          "private raw complaint narrative three", "private raw complaint narrative four"],
            "product": ["Credit card", "Credit card", "Checking", "Checking"],
            "issue": ["Payment", "Payment", "Transfer", "Transfer"],
        })
        model = MiniBatchKMeans(n_clusters=2, random_state=42, n_init=1)
        model.cluster_centers_ = np.array([[0.8, 0.2], [0.1, 0.9]])
        model.n_clusters = 2
        labels = np.array([0, 0, 1, 1])
        profiles = create_cluster_profiles(sample, labels, model, np.array(["payment", "transfer"]))
        self.assertEqual(int(profiles["sample_complaints"].sum()), 4)
        exported = profiles.to_csv(index=False)
        self.assertNotIn("private raw complaint", exported)


if __name__ == "__main__":
    unittest.main()
