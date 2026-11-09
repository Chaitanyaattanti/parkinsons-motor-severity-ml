"""Frequency-domain feature extraction with strict Nyquist gating.

Calculates power spectral density, observable band power, dominant frequency,
and spectral entropy only when physically and mathematically justified by
the verified sampling rate.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.preprocessing import ProcessedSignal


def extract_frequency_features(
    proc: ProcessedSignal,
    config: PipelineConfig | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Extract validated frequency-domain features with Nyquist and bandwidth gating.
    
    Returns:
        (features_dict, metadata_reasons_dict)
    """
    cfg = config or DEFAULT_CONFIG
    y = proc.signal_detrended
    fs = proc.fs_effective
    n = len(y)

    features: dict[str, float] = {}
    reasons: dict[str, str] = {}

    # Initial safety check
    if n < 16 or np.isnan(fs) or fs <= 1.0:
        return _empty_freq_features("INSUFFICIENT_SAMPLES_OR_INVALID_FS")

    nyquist_hz = fs / 2.0

    # Compute Welch Power Spectral Density
    # Choose segment length adapted to sample count
    nperseg = min(256, n)
    if nperseg < 8:
        return _empty_freq_features("SEGMENT_TOO_SHORT")

    freqs, psd = welch(y, fs=fs, nperseg=nperseg, detrend=False, scaling="density")

    # Observable band: [0.5 Hz, (nyquist - 0.05) Hz]
    max_observable_freq = nyquist_hz - 0.05
    obs_mask = (freqs >= cfg.min_observable_frequency_hz) & (freqs <= max_observable_freq)

    if not obs_mask.any() or np.sum(psd[obs_mask]) <= 1e-18:
        return _empty_freq_features("ZERO_OR_UNOBSERVABLE_SPECTRAL_POWER")

    obs_freqs = freqs[obs_mask]
    obs_psd = psd[obs_mask]

    # 1. Dominant Frequency in observable band
    dom_idx = np.argmax(obs_psd)
    features["dominant_frequency_hz"] = float(obs_freqs[dom_idx])
    reasons["dominant_frequency_hz"] = f"Peak in observable range [0.5, {max_observable_freq:.2f}] Hz"

    # 2. Spectral Centroid
    features["spectral_centroid_hz"] = float(np.sum(obs_freqs * obs_psd) / np.sum(obs_psd))
    reasons["spectral_centroid_hz"] = "Spectral center of mass"

    # 3. Spectral Entropy
    norm_psd = obs_psd / np.sum(obs_psd)
    norm_psd = norm_psd[norm_psd > 0]
    entropy = -np.sum(norm_psd * np.log2(norm_psd))
    max_entropy = np.log2(len(obs_psd)) if len(obs_psd) > 1 else 1.0
    features["spectral_entropy"] = float(entropy / max_entropy) if max_entropy > 0 else 0.0
    reasons["spectral_entropy"] = "Normalized Shannon entropy of power spectrum"

    # 4. Low-Frequency Voluntary Movement Band (0.5 - 3.0 Hz)
    low_mask = (freqs >= 0.5) & (freqs < 3.0) & (freqs <= nyquist_hz)
    if low_mask.any():
        p_low = float(np.trapz(psd[low_mask], freqs[low_mask])) if len(freqs[low_mask]) > 1 else float(psd[low_mask][0])
        features["band_power_low_0_5_to_3_0_hz"] = p_low
        reasons["band_power_low_0_5_to_3_0_hz"] = "Trapezoidal power integration 0.5-3.0 Hz"
    else:
        features["band_power_low_0_5_to_3_0_hz"] = np.nan
        reasons["band_power_low_0_5_to_3_0_hz"] = "BAND_UNOBSERVABLE"

    # 5. Parkinsonian Resting Tremor Band (3.0 - 5.0 Hz)
    # Observable if Nyquist >= 4.5 Hz (e.g. fs >= 9 Hz)
    if nyquist_hz >= 4.5:
        pd_mask = (freqs >= 3.0) & (freqs <= min(5.0, nyquist_hz))
        if pd_mask.any() and len(freqs[pd_mask]) > 1:
            p_pd = float(np.trapz(psd[pd_mask], freqs[pd_mask]))
            features["band_power_parkinsonian_3_0_to_5_0_hz"] = p_pd
            reasons["band_power_parkinsonian_3_0_to_5_0_hz"] = f"Observable Parkinsonian band 3.0-{min(5.0, nyquist_hz):.1f} Hz"
        else:
            features["band_power_parkinsonian_3_0_to_5_0_hz"] = np.nan
            reasons["band_power_parkinsonian_3_0_to_5_0_hz"] = "INSUFFICIENT_FREQUENCY_BINS"
    else:
        features["band_power_parkinsonian_3_0_to_5_0_hz"] = np.nan
        reasons["band_power_parkinsonian_3_0_to_5_0_hz"] = f"UNSUPPORTED_NYQUIST_LIMIT: Nyquist is {nyquist_hz:.1f}Hz < 4.5Hz"

    # 6. High Postural/Kinetic Tremor Band (5.0 - 10.0 Hz)
    # Strictly gated: requires Nyquist >= 10.0 Hz (fs >= 20.0 Hz)
    if nyquist_hz >= 10.0:
        high_mask = (freqs >= 5.0) & (freqs <= 10.0)
        if high_mask.any() and len(freqs[high_mask]) > 1:
            features["band_power_high_5_0_to_10_0_hz"] = float(np.trapz(psd[high_mask], freqs[high_mask]))
            reasons["band_power_high_5_0_to_10_0_hz"] = "Full 5.0-10.0 Hz band supported by fs >= 20 Hz"
        else:
            features["band_power_high_5_0_to_10_0_hz"] = np.nan
            reasons["band_power_high_5_0_to_10_0_hz"] = "INSUFFICIENT_BINS"
    else:
        features["band_power_high_5_0_to_10_0_hz"] = np.nan
        reasons["band_power_high_5_0_to_10_0_hz"] = f"UNSUPPORTED_NYQUIST_LIMIT: Sampling rate {fs:.1f} Hz has Nyquist {nyquist_hz:.1f} Hz < 10.0 Hz"

    # 7. Tremor Band Ratio
    p_low_val = features.get("band_power_low_0_5_to_3_0_hz", np.nan)
    p_pd_val = features.get("band_power_parkinsonian_3_0_to_5_0_hz", np.nan)
    if not np.isnan(p_low_val) and not np.isnan(p_pd_val) and p_low_val > 1e-15:
        features["tremor_power_ratio"] = float(p_pd_val / p_low_val)
        reasons["tremor_power_ratio"] = "Ratio of 3-5 Hz power to 0.5-3 Hz power"
    else:
        features["tremor_power_ratio"] = np.nan
        reasons["tremor_power_ratio"] = "RATIO_UNAVAILABLE"

    return features, reasons


def _empty_freq_features(reason: str) -> tuple[dict[str, float], dict[str, str]]:
    names = [
        "dominant_frequency_hz",
        "spectral_centroid_hz",
        "spectral_entropy",
        "band_power_low_0_5_to_3_0_hz",
        "band_power_parkinsonian_3_0_to_5_0_hz",
        "band_power_high_5_0_to_10_0_hz",
        "tremor_power_ratio",
    ]
    return {k: np.nan for k in names}, {k: reason for k in names}
