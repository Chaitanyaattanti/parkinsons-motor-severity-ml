"""Task-specific feature engineering module for Parkinson's motor assessment.

Extracts clinically motivated biomechanical and functional movement metrics
customized to the specific motor task protocol.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.preprocessing import ProcessedSignal


def extract_task_specific_features(
    proc: ProcessedSignal,
    config: PipelineConfig | None = None,
) -> dict[str, float]:
    """Extract domain-specific movement metrics appropriate for the specific task."""
    cfg = config or DEFAULT_CONFIG
    task = proc.task
    y = proc.signal
    y_centered = proc.signal_centered
    t = proc.time
    fs = proc.fs_effective
    dur = proc.duration_s
    n = len(y)

    task_feats: dict[str, float] = {}

    if n < cfg.min_samples_per_trial:
        return task_feats

    # 1. Hand Resting
    if task == "Hand Resting":
        s_std = float(np.std(y, ddof=1)) if n > 1 else np.nan
        task_feats["resting_amplitude_variability"] = s_std
        task_feats["resting_rms"] = float(np.sqrt(np.mean(y**2)))
        peaks, props = find_peaks(y_centered, prominence=max(s_std * 0.4, 1e-12), distance=max(1, int(0.15 * fs)))
        task_feats["resting_peak_count"] = float(len(peaks))
        task_feats["resting_peak_prominence"] = float(np.mean(props["prominences"])) if len(peaks) > 0 else 0.0

    # 2. Arm Extended Forward (Postural tremor & fatigue)
    elif task == "Arm Extended Forward":
        task_feats["postural_tremor_variability"] = float(np.std(y, ddof=1)) if n > 1 else np.nan
        # Linear drift slope
        if n >= 10 and dur > 0:
            slope, _ = np.polyfit(t - t[0], y, deg=1)
            task_feats["postural_drift_slope"] = float(slope)
        else:
            task_feats["postural_drift_slope"] = np.nan

        # Fatigue ratio (second half RMS / first half RMS)
        half_idx = n // 2
        if half_idx >= 4:
            rms_h1 = float(np.sqrt(np.mean(y[:half_idx]**2)))
            rms_h2 = float(np.sqrt(np.mean(y[half_idx:]**2)))
            task_feats["postural_fatigue_ratio"] = float(rms_h2 / rms_h1) if rms_h1 > 1e-12 else np.nan
        else:
            task_feats["postural_fatigue_ratio"] = np.nan

    # 3. Finger Tapping
    elif task == "Finger Tapping":
        # Detect individual taps
        s_std = float(np.std(y, ddof=1)) if n > 1 else np.nan
        prom_thresh = max(s_std * 0.5, 1e-4)
        min_dist = max(1, int(0.12 * fs))  # Min interval between taps ~ 120ms (max ~8 taps/s)
        peaks, props = find_peaks(y_centered, prominence=prom_thresh, distance=min_dist)
        n_taps = len(peaks)
        task_feats["tap_count"] = float(n_taps)
        task_feats["tap_rate_hz"] = float(n_taps / dur) if dur > 0 else np.nan

        if n_taps > 0 and "prominences" in props:
            proms = props["prominences"]
            task_feats["tap_amplitude_mean"] = float(np.mean(proms))
            task_feats["tap_amplitude_std"] = float(np.std(proms, ddof=1)) if len(proms) > 1 else 0.0

            # Bradykinetic amplitude decrement (slope across taps)
            if n_taps >= 4:
                tap_indices = np.arange(n_taps)
                slope, _ = np.polyfit(tap_indices, proms, deg=1)
                task_feats["tap_amplitude_decrement_slope"] = float(slope)
            else:
                task_feats["tap_amplitude_decrement_slope"] = np.nan
        else:
            task_feats["tap_amplitude_mean"] = np.nan
            task_feats["tap_amplitude_std"] = np.nan
            task_feats["tap_amplitude_decrement_slope"] = np.nan

        if n_taps >= 2:
            tap_times = t[peaks]
            intervals = np.diff(tap_times)
            intervals = intervals[intervals > 0]
            if len(intervals) > 0:
                mean_int = float(np.mean(intervals))
                std_int = float(np.std(intervals, ddof=1)) if len(intervals) > 1 else 0.0
                task_feats["tap_interval_mean_s"] = mean_int
                task_feats["tap_interval_cv"] = float(std_int / mean_int) if mean_int > 0 else np.nan
            else:
                task_feats["tap_interval_mean_s"] = np.nan
                task_feats["tap_interval_cv"] = np.nan
        else:
            task_feats["tap_interval_mean_s"] = np.nan
            task_feats["tap_interval_cv"] = np.nan

    # 4. Finger to Nose (Smoothness, jerk proxy, consistency)
    elif task == "Finger to Nose":
        task_feats["movement_amplitude_range"] = float(np.ptp(y))
        dt = np.diff(t)
        dy = np.diff(y)
        if (dt > 0).all() and len(dy) > 4:
            v = dy / dt
            dt_v = dt[:-1]
            a = np.diff(v) / dt_v
            jerk = np.diff(a) / dt_v[:-1]
            task_feats["movement_smoothness_jerk_proxy"] = float(np.sqrt(np.mean(jerk**2)) / dur) if dur > 0 else np.nan
        else:
            task_feats["movement_smoothness_jerk_proxy"] = np.nan

    # 5. Normal Walking & Turning Task
    elif task in ["Normal Walking", "Turning Task"]:
        # Threshold crossings / cyclic foot contacts
        threshold = np.mean(y) + 0.3 * np.std(y)
        contacts = np.flatnonzero((y[:-1] <= threshold) & (y[1:] > threshold)) + 1
        n_steps = len(contacts)
        task_feats["gait_step_count_proxy"] = float(n_steps)
        task_feats["gait_cadence_steps_per_min"] = float((n_steps / dur) * 60.0) if dur > 0 else np.nan

        if n_steps >= 2:
            step_times = t[contacts]
            step_intervals = np.diff(step_times)
            step_intervals = step_intervals[step_intervals > 0]
            if len(step_intervals) > 0:
                mean_st = float(np.mean(step_intervals))
                std_st = float(np.std(step_intervals, ddof=1)) if len(step_intervals) > 1 else 0.0
                task_feats["gait_step_time_mean_s"] = mean_st
                task_feats["gait_step_time_cv"] = float(std_st / mean_st) if mean_st > 0 else np.nan
            else:
                task_feats["gait_step_time_mean_s"] = np.nan
                task_feats["gait_step_time_cv"] = np.nan
        else:
            task_feats["gait_step_time_mean_s"] = np.nan
            task_feats["gait_step_time_cv"] = np.nan

        if task == "Turning Task":
            task_feats["turning_duration_s"] = dur
            task_feats["turning_movement_energy"] = float(np.sum(y**2))

    # 6. Quiet Standing (Postural stability)
    elif task == "Quiet Standing":
        sway_std = float(np.std(y, ddof=1)) if n > 1 else np.nan
        task_feats["postural_sway_variability"] = sway_std
        dy = np.diff(y)
        dt = np.diff(t)
        if (dt > 0).all() and len(dy) > 0:
            sway_vel = dy / dt
            task_feats["postural_sway_velocity_proxy"] = float(np.mean(np.abs(sway_vel)))
        else:
            task_feats["postural_sway_velocity_proxy"] = np.nan

        if n >= 10 and dur > 0:
            slope, _ = np.polyfit(t - t[0], y, deg=1)
            task_feats["postural_sway_drift_slope"] = float(slope)
        else:
            task_feats["postural_sway_drift_slope"] = np.nan

    # 7. Sit-to-Stand & TUG
    elif task in ["Sit-to-Stand", "TUG"]:
        task_feats["transition_duration_s"] = dur
        task_feats["transition_peak_amplitude"] = float(np.max(np.abs(y)))
        task_feats["transition_movement_energy"] = float(np.sum(y**2))

    # 8. Pronation Supination & Fist Open and Close
    elif task in ["Pronation Supination", "Fist Open and Close"]:
        s_std = float(np.std(y, ddof=1)) if n > 1 else np.nan
        peaks, props = find_peaks(y_centered, prominence=max(s_std * 0.4, 1e-4), distance=max(1, int(0.18 * fs)))
        n_reps = len(peaks)
        task_feats["repetition_count"] = float(n_reps)
        task_feats["repetition_rate_hz"] = float(n_reps / dur) if dur > 0 else np.nan

        if n_reps >= 2:
            rep_times = t[peaks]
            intervals = np.diff(rep_times)
            intervals = intervals[intervals > 0]
            if len(intervals) > 0:
                mean_int = float(np.mean(intervals))
                std_int = float(np.std(intervals, ddof=1)) if len(intervals) > 1 else 0.0
                task_feats["repetition_interval_cv"] = float(std_int / mean_int) if mean_int > 0 else np.nan
            else:
                task_feats["repetition_interval_cv"] = np.nan
        else:
            task_feats["repetition_interval_cv"] = np.nan

        if n_reps > 0 and "prominences" in props:
            proms = props["prominences"]
            mean_prom = float(np.mean(proms))
            std_prom = float(np.std(proms, ddof=1)) if len(proms) > 1 else 0.0
            task_feats["repetition_amplitude_cv"] = float(std_prom / mean_prom) if mean_prom > 0 else np.nan
        else:
            task_feats["repetition_amplitude_cv"] = np.nan

    return task_feats

