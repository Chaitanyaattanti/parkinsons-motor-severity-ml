"""Time-series windowing and temporal stability feature module.

Segments continuous sensor recordings into sliding windows while strictly
preserving participant identity and grouping to prevent data leakage.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.common_features import extract_common_features
from src.config import DEFAULT_CONFIG, PipelineConfig
from src.frequency_features import extract_frequency_features
from src.preprocessing import ProcessedSignal


def extract_windowed_features(
    proc: ProcessedSignal,
    window_duration_s: float = 10.0,
    overlap_ratio: float = 0.5,
    config: PipelineConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Segment a recording into sliding windows and compute window-level and stability metrics.
    
    Returns:
        (window_features_df, recording_stability_features_dict)
    """
    cfg = config or DEFAULT_CONFIG
    t = proc.time
    y = proc.signal
    y_c = proc.signal_centered
    y_d = proc.signal_detrended
    r = proc.raw_resistance
    fs = proc.fs_effective
    total_dur = proc.duration_s

    # If trial duration is shorter than window duration, return single window or empty
    if total_dur < window_duration_s or len(y) < cfg.min_samples_per_trial:
        return pd.DataFrame(), {}

    step_s = window_duration_s * (1.0 - overlap_ratio)
    step_samples = max(1, int(step_s * fs))
    win_samples = max(cfg.min_samples_per_trial, int(window_duration_s * fs))

    window_records: list[dict[str, Any]] = []
    window_stds: list[float] = []
    window_rms: list[float] = []
    window_pds: list[float] = []

    start_idx = 0
    win_id = 0
    while start_idx + win_samples <= len(y):
        end_idx = start_idx + win_samples
        t_win = t[start_idx:end_idx]
        y_win = y[start_idx:end_idx]
        yc_win = y_c[start_idx:end_idx]
        yd_win = y_d[start_idx:end_idx]
        r_win = r[start_idx:end_idx] if len(r) == len(y) else np.full_like(y_win, np.nan)

        # Create sub-window ProcessedSignal
        win_proc = ProcessedSignal(
            participant_id=proc.participant_id,
            task=proc.task,
            file_path=proc.file_path,
            time=t_win,
            signal=y_win,
            signal_centered=yc_win,
            signal_detrended=yd_win,
            raw_resistance=r_win,
            fs_effective=fs,
            dt_median=proc.dt_median,
            qc_report=proc.qc_report,
        )

        win_common = extract_common_features(win_proc, cfg)
        win_freq, _ = extract_frequency_features(win_proc, cfg)

        w_record = {
            "participant_id": proc.participant_id,
            "task": proc.task,
            "file_path": proc.file_path,
            "window_id": win_id,
            "window_start_s": float(t_win[0]),
            "window_end_s": float(t_win[-1]),
            "window_duration_s": float(t_win[-1] - t_win[0]),
        }
        w_record.update(win_common)
        w_record.update(win_freq)
        window_records.append(w_record)

        if not np.isnan(win_common.get("signal_std", np.nan)):
            window_stds.append(win_common["signal_std"])
        if not np.isnan(win_common.get("signal_rms", np.nan)):
            window_rms.append(win_common["signal_rms"])
        if not np.isnan(win_freq.get("band_power_parkinsonian_3_0_to_5_0_hz", np.nan)):
            window_pds.append(win_freq["band_power_parkinsonian_3_0_to_5_0_hz"])

        win_id += 1
        start_idx += step_samples

    df_windows = pd.DataFrame(window_records)

    # Compute recording-level stability metrics across windows
    stability_feats: dict[str, float] = {}
    if len(window_stds) >= 2:
        stability_feats["window_std_variability_over_time"] = float(np.std(window_stds, ddof=1))
        stability_feats["window_std_max_to_min_ratio"] = float(np.max(window_stds) / max(np.min(window_stds), 1e-12))
    else:
        stability_feats["window_std_variability_over_time"] = np.nan
        stability_feats["window_std_max_to_min_ratio"] = np.nan

    if len(window_rms) >= 2:
        # Linear slope of RMS across consecutive windows (quantifies fatigue / drift)
        win_indices = np.arange(len(window_rms))
        slope, _ = np.polyfit(win_indices, window_rms, deg=1)
        stability_feats["window_rms_drift_slope"] = float(slope)
    else:
        stability_feats["window_rms_drift_slope"] = np.nan

    if len(window_pds) >= 2:
        stability_feats["window_tremor_power_stability_cv"] = float(
            np.std(window_pds, ddof=1) / max(np.mean(window_pds), 1e-12)
        )
    else:
        stability_feats["window_tremor_power_stability_cv"] = np.nan

    return df_windows, stability_feats

