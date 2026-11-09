"""Common signal feature extraction for Parkinson's motor severity pipeline.

Calculates statistical, first-difference, amplitude, zero-crossing, and peak features
from validated, preprocessed resistance signals.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks
from scipy.stats import kurtosis, skew

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.preprocessing import ProcessedSignal


def extract_common_features(proc: ProcessedSignal, config: PipelineConfig | None = None) -> dict[str, float]:
    """Extract standard statistical and time-domain features from a ProcessedSignal."""
    cfg = config or DEFAULT_CONFIG
    y = proc.signal
    y_centered = proc.signal_centered
    t = proc.time
    fs = proc.fs_effective
    dur = proc.duration_s
    n = len(y)

    features: dict[str, float] = {}

    # Safety check: if signal is too short or invalid, return NaNs
    if n < cfg.min_samples_per_trial:
        return _empty_common_features()

    # --- A. Basic Statistical Features ---
    features["signal_mean"] = float(np.mean(y))
    features["signal_median"] = float(np.median(y))
    features["signal_std"] = float(np.std(y, ddof=cfg.ddof)) if n > 1 else np.nan
    features["signal_var"] = float(np.var(y, ddof=cfg.ddof)) if n > 1 else np.nan
    features["signal_min"] = float(np.min(y))
    features["signal_max"] = float(np.max(y))
    features["signal_range"] = float(np.ptp(y))
    features["signal_rms"] = float(np.sqrt(np.mean(y**2)))
    features["signal_abs_mean"] = float(np.mean(np.abs(y)))
    features["signal_mad_mean"] = float(np.mean(np.abs(y - np.mean(y))))
    features["signal_mad_median"] = float(np.median(np.abs(y - np.median(y))))

    p10, p25, p75, p90 = np.percentile(y, [10, 25, 75, 90])
    features["signal_p10"] = float(p10)
    features["signal_p25"] = float(p25)
    features["signal_p75"] = float(p75)
    features["signal_p90"] = float(p90)
    features["signal_iqr"] = float(p75 - p25)

    s_std = features["signal_std"]
    if n >= 8 and s_std > 1e-12:
        features["signal_skewness"] = float(skew(y, bias=False))
        features["signal_kurtosis"] = float(kurtosis(y, fisher=True, bias=False))
    else:
        features["signal_skewness"] = np.nan
        features["signal_kurtosis"] = np.nan

    # --- B. First-Difference & Signal-Change Features ---
    dy = np.diff(y)
    dt = np.diff(t)
    dt_valid = dt > 0

    features["diff_mean"] = float(np.mean(dy))
    features["diff_std"] = float(np.std(dy, ddof=cfg.ddof)) if len(dy) > 1 else np.nan
    features["diff_abs_mean"] = float(np.mean(np.abs(dy)))
    features["diff_rms"] = float(np.sqrt(np.mean(dy**2)))
    features["diff_abs_max"] = float(np.max(np.abs(dy)))

    d2y = np.diff(dy)
    features["diff2_std"] = float(np.std(d2y, ddof=cfg.ddof)) if len(d2y) > 1 else np.nan

    tot_var = float(np.sum(np.abs(dy)))
    features["total_variation"] = tot_var
    features["normalized_total_variation"] = float(tot_var / dur) if dur > 0 else np.nan

    if dt_valid.all() and len(dy) > 0:
        deriv = dy / dt
        features["derivative_abs_mean"] = float(np.mean(np.abs(deriv)))
        features["derivative_rms"] = float(np.sqrt(np.mean(deriv**2)))
    else:
        features["derivative_abs_mean"] = np.nan
        features["derivative_rms"] = np.nan

    # --- C. Distribution & Amplitude Features ---
    features["robust_amplitude_range"] = float(p90 - p10)

    mean_abs = abs(features["signal_mean"])
    if mean_abs >= cfg.cv_min_mean_threshold and not np.isnan(s_std):
        features["coefficient_of_variation"] = float(s_std / mean_abs)
    else:
        features["coefficient_of_variation"] = np.nan

    rms_val = features["signal_rms"]
    if rms_val > 1e-12:
        features["crest_factor"] = float(np.max(np.abs(y)) / rms_val)
    else:
        features["crest_factor"] = np.nan

    # --- D. Zero-Crossing & Baseline-Crossing Features ---
    # Crossing of mean-centered baseline
    crossings = np.flatnonzero(np.diff(np.signbit(y_centered)))
    zc_count = int(len(crossings))
    features["zero_crossing_count"] = float(zc_count)
    features["zero_crossing_rate"] = float(zc_count / dur) if dur > 0 else np.nan

    # --- E. Peak & Oscillation Features ---
    prom_thresh = max(s_std * cfg.peak_prominence_std_factor, 1e-12) if not np.isnan(s_std) else 1e-12
    min_dist_samples = max(1, int(cfg.peak_min_distance_s * fs)) if not np.isnan(fs) and fs > 0 else 2

    peaks, properties = find_peaks(y_centered, prominence=prom_thresh, distance=min_dist_samples)
    n_peaks = len(peaks)
    features["peak_count"] = float(n_peaks)
    features["peak_rate_per_sec"] = float(n_peaks / dur) if dur > 0 else np.nan

    if n_peaks > 0 and "prominences" in properties and len(properties["prominences"]) > 0:
        proms = properties["prominences"]
        features["peak_prominence_mean"] = float(np.mean(proms))
    else:
        features["peak_prominence_mean"] = np.nan

    if n_peaks >= 2:
        peak_times = t[peaks]
        inter_peak_intervals = np.diff(peak_times)
        inter_peak_intervals = inter_peak_intervals[inter_peak_intervals > 0]
        if len(inter_peak_intervals) > 0:
            mean_ipi = float(np.mean(inter_peak_intervals))
            std_ipi = float(np.std(inter_peak_intervals, ddof=1)) if len(inter_peak_intervals) > 1 else 0.0
            features["peak_interval_mean_s"] = mean_ipi
            features["peak_interval_cv"] = float(std_ipi / mean_ipi) if mean_ipi > 0 else np.nan
        else:
            features["peak_interval_mean_s"] = np.nan
            features["peak_interval_cv"] = np.nan
    else:
        features["peak_interval_mean_s"] = np.nan
        features["peak_interval_cv"] = np.nan

    return features


def _empty_common_features() -> dict[str, float]:
    """Return dictionary with NaN for all common features when trial is invalid."""
    names = [
        "signal_mean", "signal_median", "signal_std", "signal_var", "signal_min",
        "signal_max", "signal_range", "signal_rms", "signal_abs_mean", "signal_mad_mean",
        "signal_mad_median", "signal_p10", "signal_p25", "signal_p75", "signal_p90",
        "signal_iqr", "signal_skewness", "signal_kurtosis", "diff_mean", "diff_std",
        "diff_abs_mean", "diff_rms", "diff_abs_max", "diff2_std", "total_variation",
        "normalized_total_variation", "derivative_abs_mean", "derivative_rms",
        "robust_amplitude_range", "coefficient_of_variation", "crest_factor",
        "zero_crossing_count", "zero_crossing_rate", "peak_count", "peak_rate_per_sec",
        "peak_prominence_mean", "peak_interval_mean_s", "peak_interval_cv",
    ]
    return {k: np.nan for k in names}

