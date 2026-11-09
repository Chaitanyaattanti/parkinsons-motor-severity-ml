"""Unit tests for feature extraction correctness and Nyquist frequency limits."""

import unittest
import numpy as np
import pandas as pd

from src.common_features import extract_common_features
from src.config import PipelineConfig
from src.frequency_features import extract_frequency_features
from src.preprocessing import ProcessedSignal
from src.signal_validation import SignalQualityReport


class TestFeatureExtraction(unittest.TestCase):
    """Test feature calculations, numerical safety, and Nyquist gating (Requirements 6, 7, 11, 12)."""

    def _create_mock_signal(
        self,
        y: np.ndarray,
        fs: float = 10.0,
        task: str = "Hand Resting",
    ) -> ProcessedSignal:
        dt = 1.0 / fs
        t = np.arange(len(y)) * dt
        y_centered = y - np.mean(y)
        qc = SignalQualityReport(
            file_path="mock.csv",
            participant_id="P_MOCK",
            task=task,
            signal_selected="ΔR/R0",
            signal_selection_reason="Mock",
            n_raw_samples=len(y),
            n_valid_samples=len(y),
            n_missing_samples=0,
            pct_missing=0.0,
            n_duplicate_timestamps=0,
            n_non_monotonic_timestamps=0,
            time_span_s=float(t[-1] - t[0]) if len(t) > 1 else 0.0,
            median_dt_s=dt,
            std_dt_s=0.0,
            cv_dt=0.0,
            estimated_fs_hz=fs,
            n_gaps=0,
            total_gap_duration_s=0.0,
            max_gap_duration_s=0.0,
            is_constant_signal=False,
            signal_variance=float(np.var(y, ddof=1)),
            signal_min=float(np.min(y)),
            signal_max=float(np.max(y)),
            signal_range=float(np.ptp(y)),
            n_clipped_samples=0,
            pct_clipped=0.0,
            longest_flat_section_samples=0,
            longest_flat_section_duration_s=0.0,
            quality_status="PASSED",
        )
        return ProcessedSignal(
            participant_id="P_MOCK",
            task=task,
            file_path="mock.csv",
            time=t,
            signal=y,
            signal_centered=y_centered,
            signal_detrended=y_centered.copy(),
            raw_resistance=np.full_like(y, np.nan),
            fs_effective=fs,
            dt_median=dt,
            qc_report=qc,
        )

    def test_06_non_finite_feature_outputs_safe_handling(self) -> None:
        """Requirement 6: Safe handling of zero-mean signals (CV does not blow up to inf)."""
        # Symmetric signal around 0.0 -> mean is 0.0
        y = np.array([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
        proc = self._create_mock_signal(y, fs=10.0)
        feats = extract_common_features(proc)
        # CV should be NaN (safeguarded against division by zero), not inf or -inf
        self.assertTrue(np.isnan(feats["coefficient_of_variation"]))
        self.assertFalse(np.isinf(feats["coefficient_of_variation"]))
        self.assertFalse(np.isinf(feats["signal_mean"]))
        self.assertFalse(np.isinf(feats["crest_factor"]))

    def test_07_correct_calculation_of_basic_statistical_features(self) -> None:
        """Requirement 7: Basic statistical features match exact mathematical definitions."""
        # Known test signal: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = np.arange(1.0, 11.0)
        proc = self._create_mock_signal(y, fs=10.0)
        feats = extract_common_features(proc)

        # Analytical checks
        self.assertAlmostEqual(feats["signal_mean"], 5.5)
        self.assertAlmostEqual(feats["signal_median"], 5.5)
        # Sample variance with ddof=1: sum((y-5.5)^2)/9 = 82.5/9 = 9.166666...
        self.assertAlmostEqual(feats["signal_var"], 82.5 / 9.0)
        self.assertAlmostEqual(feats["signal_std"], np.sqrt(82.5 / 9.0))
        # RMS: sqrt(sum(y^2)/10) = sqrt(385/10) = sqrt(38.5)
        self.assertAlmostEqual(feats["signal_rms"], np.sqrt(38.5))
        self.assertAlmostEqual(feats["signal_range"], 9.0)
        self.assertAlmostEqual(feats["signal_min"], 1.0)
        self.assertAlmostEqual(feats["signal_max"], 10.0)
        # IQR: 75th percentile (7.75) - 25th percentile (3.25) = 4.5
        self.assertAlmostEqual(feats["signal_iqr"], 4.5)

    def test_11_and_12_frequency_features_nyquist_and_unsupported_bands(self) -> None:
        """Requirements 11 & 12: Frequency features obey Nyquist cutoff; unsupported bands return NaN."""
        # 1. Test at fs = 10 Hz (Nyquist = 5.0 Hz)
        # Create 10-second 3 Hz sine wave (observable)
        fs_10 = 10.0
        t_10 = np.arange(0, 10, 1.0 / fs_10)
        y_3hz = np.sin(2 * np.pi * 3.0 * t_10)

        proc_10 = self._create_mock_signal(y_3hz, fs=fs_10)
        feats_10, reasons_10 = extract_frequency_features(proc_10)

        # Dominant frequency should be close to 3.0 Hz
        self.assertAlmostEqual(feats_10["dominant_frequency_hz"], 3.0, delta=0.4)
        # Parkinsonian band (3-5 Hz) should be valid
        self.assertFalse(np.isnan(feats_10["band_power_parkinsonian_3_0_to_5_0_hz"]))
        # High tremor band (5-10 Hz) MUST be NaN because Nyquist=5.0Hz cannot observe > 5Hz!
        self.assertTrue(np.isnan(feats_10["band_power_high_5_0_to_10_0_hz"]))
        self.assertIn("UNSUPPORTED_NYQUIST_LIMIT", reasons_10["band_power_high_5_0_to_10_0_hz"])

        # 2. Test at fs = 25 Hz (Nyquist = 12.5 Hz >= 10.0 Hz)
        fs_25 = 25.0
        t_25 = np.arange(0, 10, 1.0 / fs_25)
        y_6hz = np.sin(2 * np.pi * 6.0 * t_25)
        proc_25 = self._create_mock_signal(y_6hz, fs=fs_25)
        feats_25, reasons_25 = extract_frequency_features(proc_25)

        # High tremor band (5-10 Hz) IS supported at fs=25Hz
        self.assertFalse(np.isnan(feats_25["band_power_high_5_0_to_10_0_hz"]))
        self.assertAlmostEqual(feats_25["dominant_frequency_hz"], 6.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()

