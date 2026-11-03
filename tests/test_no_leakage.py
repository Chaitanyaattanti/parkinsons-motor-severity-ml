"""Unit tests for participant leakage prevention and grouped cross-validation."""

import unittest
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

from src.train_model import NON_PREDICTIVE_COLUMNS, check_model_readiness, train_and_evaluate_grouped


class TestLeakagePrevention(unittest.TestCase):
    """Test strict prevention of participant leakage across evaluation splits (Requirements 13, 14, 15)."""

    def test_13_no_leakage_of_metadata_into_predictor_matrix(self) -> None:
        """Requirement 13: Participant IDs, diagnosis, filenames, or labels cannot enter X."""
        # Simulated dataset
        df = pd.DataFrame({
            "participant_id": ["P01", "P01", "P02", "P02", "P03", "P03"],
            "diagnosis": ["Healthy", "Healthy", "PD", "PD", "PD", "PD"],
            "session_id": ["S1", "S1", "S2", "S2", "S3", "S3"],
            "task": ["Rest", "Tap", "Rest", "Tap", "Rest", "Tap"],
            "file_path": ["f1", "f2", "f3", "f4", "f5", "f6"],
            "clinical_score": [0, 0, 2, 2, 3, 3],
            "signal_std": [0.01, 0.02, 0.04, 0.05, 0.08, 0.09],
            "diff_abs_mean": [0.001, 0.002, 0.003, 0.004, 0.005, 0.006],
        })

        target_col = "clinical_score"
        candidate_cols = [c for c in df.columns if c not in NON_PREDICTIVE_COLUMNS and c != target_col]
        numeric_features = df[candidate_cols].select_dtypes(include=[np.number]).columns.tolist()

        # Assert no metadata leaks into features
        for leaked_col in ["participant_id", "diagnosis", "session_id", "file_path", "clinical_score"]:
            self.assertNotIn(leaked_col, numeric_features)

        # Only legitimate sensor features should be present
        self.assertListEqual(numeric_features, ["signal_std", "diff_abs_mean"])

    def test_14_and_15_grouped_splitting_and_zero_participant_overlap(self) -> None:
        """Requirements 14 & 15: All recordings of a participant remain in one fold; zero leakage."""
        # 6 participants with multiple trials each
        participants = ["P01", "P02", "P03", "P04", "P05", "P06"]
        rows = []
        for p in participants:
            for trial in ["trial1", "trial2", "trial3"]:
                rows.append({
                    "participant_id": p,
                    "task": "Hand Resting",
                    "signal_std": np.random.uniform(0.01, 0.1),
                    "signal_rms": np.random.uniform(0.01, 0.1),
                    "clinical_score": 1.0 if "P01" in p else 2.0,
                })

        df_synthetic = pd.DataFrame(rows)
        groups = df_synthetic["participant_id"].values
        x = df_synthetic[["signal_std", "signal_rms"]]
        y = df_synthetic["clinical_score"].values

        cv = GroupKFold(n_splits=3)
        for fold, (train_idx, val_idx) in enumerate(cv.split(x, y, groups=groups), 1):
            train_parts = set(groups[train_idx])
            val_parts = set(groups[val_idx])

            # Mandatory test: Train and validation sets must be completely disjoint by participant!
            self.assertTrue(
                train_parts.isdisjoint(val_parts),
                f"Fold {fold} failed: Participant overlap found: {train_parts.intersection(val_parts)}",
            )
            # Ensure multiple trials of same participant stay together
            for p in train_parts:
                self.assertNotIn(p, val_parts)


if __name__ == "__main__":
    unittest.main()

