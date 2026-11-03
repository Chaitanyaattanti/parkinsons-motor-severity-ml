"""Unit tests for advanced windowing, ordinal thresholding, and task-specific models."""

import unittest
import numpy as np
import pandas as pd

from src.ordinal_classifier import OrdinalThresholdRegressor
from src.preprocessing import ProcessedSignal
from src.signal_validation import SignalQualityReport
from src.task_models import train_task_specific_model
from src.windowing import extract_windowed_features
from sklearn.linear_model import Ridge


class TestAdvancedModules(unittest.TestCase):
    """Test sliding-window feature segmentation and ordinal threshold regression."""

    def test_windowing_preserves_grouping(self) -> None:
        """Verify windowing generates sub-windows without losing participant ID."""
        t = np.arange(0, 30.0, 0.1)  # 30 seconds at 10 Hz
        y = np.sin(2 * np.pi * 3.0 * t)
        qc = SignalQualityReport(
            file_path="mock.csv", participant_id="HP001", task="Hand Resting",
            signal_selected="ΔR/R0", signal_selection_reason="Mock",
            n_raw_samples=len(y), n_valid_samples=len(y), n_missing_samples=0, pct_missing=0.0,
            n_duplicate_timestamps=0, n_non_monotonic_timestamps=0, time_span_s=29.9,
            median_dt_s=0.1, std_dt_s=0.0, cv_dt=0.0, estimated_fs_hz=10.0,
            n_gaps=0, total_gap_duration_s=0.0, max_gap_duration_s=0.0,
            is_constant_signal=False, signal_variance=0.5, signal_min=-1.0, signal_max=1.0,
            signal_range=2.0, n_clipped_samples=0, pct_clipped=0.0,
            longest_flat_section_samples=0, longest_flat_section_duration_s=0.0, quality_status="PASSED"
        )
        proc = ProcessedSignal(
            participant_id="HP001", task="Hand Resting", file_path="mock.csv",
            time=t, signal=y, signal_centered=y.copy(), signal_detrended=y.copy(),
            raw_resistance=np.full_like(y, np.nan), fs_effective=10.0, dt_median=0.1, qc_report=qc
        )
        df_win, stability = extract_windowed_features(proc, window_duration_s=10.0, overlap_ratio=0.5)

        self.assertGreater(len(df_win), 1)
        self.assertTrue((df_win["participant_id"] == "HP001").all())
        self.assertIn("window_std_variability_over_time", stability)

    def test_ordinal_threshold_regressor(self) -> None:
        """Verify ordinal thresholding outputs valid discrete integer classes in [0, 4]."""
        X = np.random.normal(size=(50, 3))
        # Continuous linear target with noise
        cont_y = X[:, 0] * 1.5 + X[:, 1] * 0.5 + 2.0
        # Discretized ordinal target (0, 1, 2, 3, 4)
        y = np.clip(np.round(cont_y), 0, 4).astype(int)

        base = Ridge(alpha=1.0)
        reg = OrdinalThresholdRegressor(base)
        reg.fit(X, y)

        preds = reg.predict(X)
        self.assertTrue(np.all((preds >= 0) & (preds <= 4)))
        self.assertTrue(np.issubdtype(preds.dtype, np.integer))


if __name__ == "__main__":
    unittest.main()

