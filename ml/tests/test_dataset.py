"""Unit tests for dataset construction and cohort ground-truth labels."""

import unittest
import numpy as np
import pandas as pd

from src.build_dataset import build_master_datasets
from src.config import PipelineConfig


class TestDatasetIntegrity(unittest.TestCase):
    """Test dataset construction rules and healthy-control labels."""

    def test_10_prevention_of_accidental_label_creation(self) -> None:
        """Healthy controls and supplied Clinical Score workbook labels are preserved."""
        df_rec, df_part_task, df_long = build_master_datasets()

        # 1. Healthy controls have the explicitly requested zero ground truth.
        hp_records = df_rec[df_rec["diagnosis"] == "Healthy"]
        self.assertTrue((hp_records["clinical_score"] == 0).all())
        self.assertTrue(
            (
                hp_records["clinical_score_source"]
                == "Healthy control ground truth (study cohort definition)"
            ).all()
        )
        self.assertTrue(
            (df_rec.loc[df_rec["diagnosis"] == "Healthy", "label_verified"] == False).all()
        )

        # 2. PD patients use the supplied task-level workbook scores.
        pd_records = df_rec[df_rec["diagnosis"] == "Parkinson's Disease"]
        self.assertTrue(pd_records["clinical_score"].notna().all())
        self.assertTrue(pd_records["label_verified"].all())

        # 3. Aggregated healthy rows retain the same ground truth.
        healthy_participant_tasks = df_part_task[
            df_part_task["diagnosis"] == "Healthy"
        ]
        self.assertTrue((healthy_participant_tasks["clinical_score"] == 0).all())


if __name__ == "__main__":
    unittest.main()
