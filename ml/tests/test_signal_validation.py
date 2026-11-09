"""Unit tests for signal validation, quality control, and edge-case detection."""

import unittest
import numpy as np
import pandas as pd

from src.signal_validation import SignalValidator


class TestSignalValidation(unittest.TestCase):
    """Test QC rules: missing data, duplicates, constancy, short signals (Requirements 2, 3, 4, 5)."""

    def setUp(self) -> None:
        self.validator = SignalValidator()

    def test_02_missing_and_invalid_values(self) -> None:
        """Requirement 2: Detection and handling of missing, NaN, and non-finite values."""
        df = pd.DataFrame({
            "Time": [0.1, 0.2, 0.3, 0.4, np.nan, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
            "ΔR/R0": [0.0, 0.01, np.inf, 0.02, 0.03, 0.04, -np.inf, 0.05, 0.02, 0.01, 0.0, 0.01, 0.02, 0.01, 0.0],
        })
        clean_df, qc = self.validator.extract_and_validate(df)
        # Non-finite rows must be excluded from clean_df
        self.assertFalse(np.isinf(clean_df["signal"].values).any())
        self.assertFalse(np.isnan(clean_df["signal"].values).any())
        self.assertGreater(qc.n_missing_samples, 0)
        self.assertEqual(len(clean_df), qc.n_valid_samples)

    def test_03_duplicate_and_irregular_timestamps(self) -> None:
        """Requirement 3: Detection of duplicate and non-monotonic timestamps."""
        df = pd.DataFrame({
            "Time": [0.1, 0.2, 0.2, 0.3, 0.5, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],  # 0.2 dup, 0.5->0.4 non-monotonic
            "ΔR/R0": [0.0, 0.01, 0.01, 0.02, 0.03, 0.02, 0.04, 0.05, 0.03, 0.02, 0.01],
        })
        clean_df, qc = self.validator.extract_and_validate(df)
        self.assertGreaterEqual(qc.n_duplicate_timestamps, 1)
        self.assertGreaterEqual(qc.n_non_monotonic_timestamps, 1)
        self.assertIn("WARNING", qc.quality_status)

    def test_04_constant_signals(self) -> None:
        """Requirement 4: Flagging of constant or nearly constant sensor signals."""
        df = pd.DataFrame({
            "Time": np.arange(0.1, 2.0, 0.1),
            "ΔR/R0": [0.005] * 19,  # Completely flat constant signal
        })
        clean_df, qc = self.validator.extract_and_validate(df)
        self.assertTrue(qc.is_constant_signal)
        self.assertEqual(qc.quality_status, "FAILED")
        self.assertIn("constant", "; ".join(qc.warnings).lower())

    def test_05_very_short_recordings(self) -> None:
        """Requirement 5: Rejection of very short signals (< 10 samples)."""
        df = pd.DataFrame({
            "Time": [0.1, 0.2, 0.3],  # Only 3 samples
            "ΔR/R0": [0.01, 0.02, 0.01],
        })
        clean_df, qc = self.validator.extract_and_validate(df)
        self.assertEqual(qc.quality_status, "FAILED")
        self.assertEqual(len(clean_df), 0)
        self.assertIn("Insufficient valid samples", "; ".join(qc.errors))


if __name__ == "__main__":
    unittest.main()
