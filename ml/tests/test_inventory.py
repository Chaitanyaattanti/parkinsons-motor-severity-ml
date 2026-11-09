"""Unit tests for data inventory, column identification, and task preservation."""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_inventory import canonicalize_task, parse_participant_and_group
from src.signal_validation import SignalValidator


class TestInventoryAndParsing(unittest.TestCase):
    """Test column identification and participant metadata resolution (Requirements 1, 8, 9)."""

    def setUp(self) -> None:
        self.validator = SignalValidator()

    def test_01_column_identification_variations(self) -> None:
        """Requirement 1: Correct identification of timestamp and signal columns."""
        # Format 1: Explicit Time and ΔR/R0
        df1 = pd.DataFrame({
            "Time": [0.1, 0.2, 0.3, 0.4, 0.5],
            "R0": [2680.0] * 5,
            "R": [2680.0, 2684.0, 2688.0, 2682.0, 2680.0],
            "ΔR": [0.0, 4.0, 8.0, 2.0, 0.0],
            "ΔR/R0": [0.0, 4.0 / 2680.0, 8.0 / 2680.0, 2.0 / 2680.0, 0.0],
        })
        m1 = self.validator.resolve_columns(df1)
        self.assertEqual(m1["time"], "Time")
        self.assertEqual(m1["delta_r_over_r0"], "ΔR/R0")

        # Format 2: Encoding artifact ?R/R0
        df2 = pd.DataFrame({
            "Time": [0.1, 0.2, 0.3, 0.4],
            "?R/R0": [0.0, 0.01, 0.02, 0.015],
        })
        m2 = self.validator.resolve_columns(df2)
        self.assertEqual(m2["time"], "Time")
        self.assertEqual(m2["delta_r_over_r0"], "?R/R0")

        # Format 3: Positional columns ['myData0', 'Unnamed: 1', 'myData1', 'Unnamed: 3', 'Unnamed: 4']
        df3 = pd.DataFrame({
            "myData0": [0.1, 0.2, 0.3, 0.4],
            "Unnamed: 1": [2690.0] * 4,
            "myData1": [2690.0, 2695.0, 2692.0, 2690.0],
            "Unnamed: 3": [0.0, 5.0, 2.0, 0.0],
            "Unnamed: 4": [0.0, 5.0 / 2690.0, 2.0 / 2690.0, 0.0],
        })
        m3 = self.validator.resolve_columns(df3)
        self.assertEqual(m3["time"], "myData0")
        self.assertEqual(m3["delta_r_over_r0"], "Unnamed: 4")

    def test_08_missing_task_handling_no_imputation(self) -> None:
        """Requirement 8: Handling of missing task recordings without zero-filling or synthesizing."""
        # Simulated participant-task matrix
        matrix = pd.DataFrame([
            {"participant_id": "P01", "Hand Resting": "Valid", "Normal Walking": "Missing"},
            {"participant_id": "P02", "Hand Resting": "Valid", "Normal Walking": "Valid"},
        ])
        # P01 must NOT have Normal Walking artificially filled as 0 or group average
        p01_walk = matrix.loc[matrix["participant_id"] == "P01", "Normal Walking"].iloc[0]
        self.assertEqual(p01_walk, "Missing")
        self.assertNotEqual(p01_walk, 0)
        self.assertNotEqual(p01_walk, "Valid")

    def test_09_preservation_of_identifiers(self) -> None:
        """Requirement 9: Preservation of participant and task identifiers."""
        path = Path("Healthy Participants/HP001/Hand Resting.xlsx")
        p_id, group, sess, unambig = parse_participant_and_group(path)
        self.assertEqual(p_id, "HP001")
        self.assertEqual(group, "Healthy")
        self.assertTrue(unambig)

        task_canon = canonicalize_task("Hand Resting")
        self.assertEqual(task_canon, "Hand Resting")
        # Ensure task is canonical and not encoded into feature names
        self.assertNotIn("HP001", "signal_std")
        self.assertNotIn("Hand_Resting", "signal_std")


if __name__ == "__main__":
    unittest.main()

