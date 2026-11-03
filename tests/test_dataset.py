"""Unit tests for dataset construction and prevention of accidental label creation."""

import unittest
import numpy as np
import pandas as pd

from src.build_dataset import build_master_datasets
from src.config import PipelineConfig


class TestDatasetIntegrity(unittest.TestCase):
    """Test dataset construction rules and label safety (Requirement 10)."""

    def test_10_prevention_of_accidental_label_creation(self) -> None:
        """Requirement 10: Prevention of accidental label creation or fake score assignment."""
        df_rec, df_part_task, df_long = build_master_datasets()

        # 1. Real recordings must NOT have fabricated clinical scores
        self.assertTrue(df_rec["clinical_score"].isna().all())
        self.assertTrue((df_rec["label_verified"] == False).all())

        # 2. Healthy participants must NOT be defaulted to 0
        hp_records = df_rec[df_rec["diagnosis"] == "Healthy"]
        self.assertTrue(hp_records["clinical_score"].isna().all())

        # 3. PD patients must NOT have diagnosis mapped to an arbitrary score
        pd_records = df_rec[df_rec["diagnosis"] == "Parkinson's Disease"]
        self.assertTrue(pd_records["clinical_score"].isna().all())

        # 4. Aggregated table must also retain unassigned label status
        self.assertTrue(df_part_task["clinical_score"].isna().all())


if __name__ == "__main__":
    unittest.main()

