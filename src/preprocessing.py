"""Preprocessing and signal preparation module.

Performs robust cleaning, deduplication, monotonic time ordering, safe gap-limited
resampling where necessary, and baseline centering while preserving the raw signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import detrend

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.signal_validation import SignalQualityReport, SignalValidator


@dataclass
class ProcessedSignal:
    """Dataclass holding cleaned, validated signal data and its QC provenance."""

    participant_id: str
    task: str
    file_path: str
    time: np.ndarray
    signal: np.ndarray  # Cleaned primary normalized signal (ΔR/R0)
    signal_centered: np.ndarray  # Mean-centered for oscillation/spectral analysis
    signal_detrended: np.ndarray  # Linear detrended
    raw_resistance: np.ndarray  # Raw resistance in Ohms, or NaN if unavailable
    fs_effective: float  # Verified sampling frequency in Hz
    dt_median: float  # Median sampling interval in seconds
    qc_report: SignalQualityReport
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        """Recording span in seconds."""
        if len(self.time) > 1:
            return float(self.time[-1] - self.time[0])
        return 0.0

    @property
    def n_samples(self) -> int:
        return len(self.signal)


class SignalPreprocessor:
    """Performs defensive preprocessing on validated raw sensor records."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.validator = SignalValidator(self.config)

    def process(
        self,
        df: pd.DataFrame,
        file_path: str = "unknown",
        participant_id: str = "UNKNOWN",
        task: str = "Unknown",
        interpolate_to_uniform: bool = False,
    ) -> ProcessedSignal:
        """Clean, deduplicate, and prepare sensor signals for feature extraction."""
        provenance: dict[str, Any] = {
            "file_path": file_path,
            "deduplication_applied": False,
            "sorting_applied": False,
            "resampling_applied": False,
            "max_permitted_gap_s": None,
            "samples_affected_by_resampling": 0,
        }

        # 1. Validation and initial channel parsing
        clean_df, qc = self.validator.extract_and_validate(df, file_path, participant_id, task)

        if len(clean_df) == 0 or qc.quality_status == "FAILED":
            # Return empty processed signal with failed QC
            return ProcessedSignal(
                participant_id=participant_id,
                task=task,
                file_path=file_path,
                time=np.array([]),
                signal=np.array([]),
                signal_centered=np.array([]),
                signal_detrended=np.array([]),
                raw_resistance=np.array([]),
                fs_effective=np.nan,
                dt_median=np.nan,
                qc_report=qc,
                provenance=provenance,
            )

        # 2. Sort by time and remove duplicate timestamps
        if qc.n_non_monotonic_timestamps > 0:
            clean_df = clean_df.sort_values("time")
            provenance["sorting_applied"] = True

        if qc.n_duplicate_timestamps > 0:
            clean_df = clean_df.drop_duplicates(subset=["time"], keep="first")
            provenance["deduplication_applied"] = True

        t = clean_df["time"].to_numpy(float)
        y = clean_df["signal"].to_numpy(float)
        r = clean_df["raw_resistance"].to_numpy(float)

        dt = np.diff(t)
        dt_pos = dt[dt > 0]
        med_dt = float(np.median(dt_pos)) if len(dt_pos) > 0 else (1.0 / self.config.nominal_fs_hz)
        fs_eff = float(1.0 / med_dt) if med_dt > 0 else self.config.nominal_fs_hz

        # 3. Optional uniform grid resampling with gap safety
        if interpolate_to_uniform and qc.cv_dt > 0.1 and len(t) > 10:
            max_gap = self.config.max_gap_factor * med_dt
            provenance["max_permitted_gap_s"] = max_gap
            
            # Create uniform grid
            t_uniform = np.arange(t[0], t[-1] + 0.5 * med_dt, med_dt)
            # Find intervals where dt > max_gap
            gaps_idx = np.flatnonzero(dt > max_gap)
            
            # Linear interpolate
            y_interp = np.interp(t_uniform, t, y)
            r_interp = np.interp(t_uniform, t, r) if np.isfinite(r).any() else np.full_like(y_interp, np.nan)
            
            # Mask out samples inside unbridgeable gaps
            for gi in gaps_idx:
                gap_start = t[gi]
                gap_end = t[gi + 1]
                mask = (t_uniform > gap_start) & (t_uniform < gap_end)
                y_interp[mask] = np.nan
                r_interp[mask] = np.nan

            valid_interp = np.isfinite(y_interp)
            provenance["resampling_applied"] = True
            provenance["samples_affected_by_resampling"] = int(np.sum(valid_interp))
            
            t = t_uniform[valid_interp]
            y = y_interp[valid_interp]
            r = r_interp[valid_interp]

        # 4. Centering and Detrending
        mean_y = float(np.mean(y)) if len(y) > 0 else 0.0
        y_centered = y - mean_y
        y_detrended = detrend(y) if len(y) > 4 else y_centered.copy()

        return ProcessedSignal(
            participant_id=participant_id,
            task=task,
            file_path=file_path,
            time=t,
            signal=y,
            signal_centered=y_centered,
            signal_detrended=y_detrended,
            raw_resistance=r,
            fs_effective=fs_eff,
            dt_median=med_dt,
            qc_report=qc,
            provenance=provenance,
        )

