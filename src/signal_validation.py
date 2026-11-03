"""Signal validation, quality control, and robust column parsing.

Inspects raw recording tables, resolves physical meanings of columns,
performs automated quality control checks, and emits detailed QC metrics.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import DEFAULT_CONFIG, PipelineConfig


@dataclass
class SignalQualityReport:
    """Dataclass holding comprehensive quality control metrics for a single recording."""

    file_path: str
    participant_id: str
    task: str
    signal_selected: str
    signal_selection_reason: str
    n_raw_samples: int
    n_valid_samples: int
    n_missing_samples: int
    pct_missing: float
    n_duplicate_timestamps: int
    n_non_monotonic_timestamps: int
    time_span_s: float
    median_dt_s: float
    std_dt_s: float
    cv_dt: float
    estimated_fs_hz: float
    n_gaps: int
    total_gap_duration_s: float
    max_gap_duration_s: float
    is_constant_signal: bool
    signal_variance: float
    signal_min: float
    signal_max: float
    signal_range: float
    n_clipped_samples: int
    pct_clipped: float
    longest_flat_section_samples: int
    longest_flat_section_duration_s: float
    quality_status: str  # PASSED, WARNING, FAILED
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["warnings"] = "; ".join(self.warnings) if self.warnings else "None"
        d["errors"] = "; ".join(self.errors) if self.errors else "None"
        return d


class SignalValidator:
    """Validates raw sensor records and produces structured signals with QC metrics."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG

    def resolve_columns(self, df: pd.DataFrame) -> dict[str, str | None]:
        """Detect the roles of DataFrame columns using robust heuristic matching."""
        mapping: dict[str, str | None] = {
            "time": None,
            "r0": None,
            "r": None,
            "delta_r": None,
            "delta_r_over_r0": None,
        }

        cols = list(df.columns)
        n_cols = len(cols)

        # 1. Look for explicit column names
        for col in cols:
            c_str = str(col).strip()
            c_lower = c_str.lower()
            if c_lower in ["time", "timestamp"]:
                mapping["time"] = col
            elif c_str in ["ΔR/R0", "?R/R0", "dR/R0"]:
                mapping["delta_r_over_r0"] = col
            elif c_str in ["ΔR", "?R", "dR"]:
                mapping["delta_r"] = col
            elif c_str == "R0":
                mapping["r0"] = col
            elif c_str == "R":
                mapping["r"] = col

        # 2. Structural position heuristics based on study recording hardware formats
        # Format A: 5 columns ['myData0', 'Unnamed: 1', 'myData1', 'Unnamed: 3', 'Unnamed: 4'] (HP002 / HP003)
        if n_cols == 5 and mapping["time"] is None and "myData0" in cols:
            mapping["time"] = "myData0"
            mapping["r0"] = cols[1]
            mapping["r"] = cols[2]
            mapping["delta_r"] = cols[3]
            mapping["delta_r_over_r0"] = cols[4]

        # Format B: 6 columns ['myData0', 'Time', 'Unnamed: 2', 'myData1', 'Unnamed: 4', 'Unnamed: 5'] (PD002)
        elif n_cols == 6 and "myData0" in cols and any(c in cols for c in ["Time", "Unnamed: 1"]):
            # myData0 is actual high-res hardware clock, Col 1 is nominal 20Hz time
            # We select myData0 if it has valid timestamps, else Col 1
            mapping["time"] = "myData0" if "myData0" in cols else cols[1]
            mapping["r0"] = cols[2]
            mapping["r"] = cols[3]
            mapping["delta_r"] = cols[4]
            mapping["delta_r_over_r0"] = cols[5]

        # Format C: 6 columns with all NaN except myData0 and myData1 (Atypical_PD001)
        elif n_cols >= 2 and "myData0" in cols and "myData1" in cols:
            mapping["time"] = "myData0"
            mapping["r"] = "myData1"

        # Format D: 2 columns ['Time', '?R/R0'] (PD001 CSV)
        elif n_cols == 2:
            if mapping["time"] is None:
                mapping["time"] = cols[0]
            if mapping["delta_r_over_r0"] is None:
                mapping["delta_r_over_r0"] = cols[1]

        # Fallback time if still None
        if mapping["time"] is None and n_cols > 0:
            mapping["time"] = cols[0]

        return mapping

    def extract_and_validate(
        self,
        df: pd.DataFrame,
        file_path: str = "unknown",
        participant_id: str = "UNKNOWN",
        task: str = "Unknown",
    ) -> tuple[pd.DataFrame, SignalQualityReport]:
        """Extract validated time and normalized signal, generating a quality report."""
        mapping = self.resolve_columns(df)
        warnings: list[str] = []
        errors: list[str] = []

        # 1. Time extraction
        time_col = mapping["time"]
        if time_col is None or time_col not in df.columns:
            errors.append("No valid timestamp column could be resolved.")
            empty_report = self._create_empty_report(file_path, participant_id, task, errors)
            return pd.DataFrame(), empty_report

        t_raw = pd.to_numeric(df[time_col], errors="coerce")
        n_raw = len(df)

        # 2. Signal extraction (prefer normalized ΔR/R0)
        signal_col_used = "none"
        selection_reason = ""
        s_raw: pd.Series | None = None
        r_raw_series: pd.Series | None = None

        if mapping["delta_r_over_r0"] is not None and mapping["delta_r_over_r0"] in df.columns:
            s_cand = pd.to_numeric(df[mapping["delta_r_over_r0"]], errors="coerce")
            if s_cand.notnull().sum() > 0:
                s_raw = s_cand
                signal_col_used = str(mapping["delta_r_over_r0"])
                selection_reason = "Direct normalized resistance change (ΔR/R0) provided by hardware export."

        # Fallback: compute from R and R0 or initial R
        if s_raw is None or s_raw.notnull().sum() == 0:
            if mapping["r"] is not None and mapping["r"] in df.columns:
                r_series = pd.to_numeric(df[mapping["r"]], errors="coerce")
                r_raw_series = r_series
                r_valid = r_series.dropna()
                if len(r_valid) > 0:
                    r0_val = None
                    if mapping["r0"] is not None and mapping["r0"] in df.columns:
                        r0_cand = pd.to_numeric(df[mapping["r0"]], errors="coerce").dropna()
                        if len(r0_cand) > 0:
                            r0_val = float(r0_cand.iloc[0])
                    if r0_val is None or r0_val <= 0:
                        r0_val = float(r_valid.iloc[0])  # Initial baseline resistance
                    
                    if r0_val > 0:
                        s_raw = (r_series - r0_val) / r0_val
                        signal_col_used = f"computed_from_{mapping['r']}"
                        selection_reason = f"Computed normalized ΔR/R0 from raw resistance R and baseline R0={r0_val:.2f} Ohms."

        if s_raw is None or s_raw.notnull().sum() == 0:
            errors.append("Could not extract or compute a valid normalized resistance signal.")
            empty_report = self._create_empty_report(file_path, participant_id, task, errors)
            return pd.DataFrame(), empty_report

        # 3. Align valid pairs
        valid_mask = t_raw.notnull() & s_raw.notnull() & np.isfinite(t_raw) & np.isfinite(s_raw)
        n_valid = int(valid_mask.sum())
        n_missing = n_raw - n_valid
        pct_missing = (n_missing / n_raw * 100.0) if n_raw > 0 else 100.0

        if n_valid < self.config.min_samples_per_trial:
            errors.append(f"Insufficient valid samples ({n_valid} < {self.config.min_samples_per_trial}).")
            empty_report = self._create_empty_report(file_path, participant_id, task, errors, n_raw, n_valid)
            return pd.DataFrame(), empty_report

        t = t_raw[valid_mask].to_numpy(float)
        y = s_raw[valid_mask].to_numpy(float)
        r_clean = r_raw_series[valid_mask].to_numpy(float) if r_raw_series is not None else np.full_like(y, np.nan)

        # 4. Timestamp analysis
        t_span = float(t[-1] - t[0])
        dt = np.diff(t)
        n_dup = int(np.sum(dt == 0))
        n_non_mono = int(np.sum(dt < 0))

        if n_non_mono > 0:
            warnings.append(f"Detected {n_non_mono} non-monotonic timestamp steps.")
        if n_dup > 0:
            warnings.append(f"Detected {n_dup} duplicate timestamps.")

        dt_pos = dt[dt > 0]
        med_dt = float(np.median(dt_pos)) if len(dt_pos) > 0 else np.nan
        std_dt = float(np.std(dt_pos)) if len(dt_pos) > 0 else np.nan
        cv_dt = float(std_dt / med_dt) if med_dt and med_dt > 0 else np.nan
        est_fs = float(1.0 / med_dt) if med_dt and med_dt > 0 else np.nan

        # Detect gaps
        gap_thresh = self.config.max_gap_factor * med_dt if med_dt and med_dt > 0 else 0.5
        gaps = dt_pos[dt_pos > gap_thresh]
        n_gaps = int(len(gaps))
        total_gap_dur = float(np.sum(gaps)) if n_gaps > 0 else 0.0
        max_gap_dur = float(np.max(gaps)) if n_gaps > 0 else 0.0

        if n_gaps > 0:
            warnings.append(f"Found {n_gaps} timestamp gaps exceeding {gap_thresh:.3f}s (max gap = {max_gap_dur:.3f}s).")

        # 5. Signal amplitude & constancy
        sig_var = float(np.var(y, ddof=1)) if len(y) > 1 else 0.0
        is_const = sig_var < self.config.constant_signal_variance_threshold
        sig_min = float(np.min(y))
        sig_max = float(np.max(y))
        sig_range = float(sig_max - sig_min)

        if is_const:
            warnings.append(f"Signal is nearly constant (variance = {sig_var:.2e} < {self.config.constant_signal_variance_threshold:.2e}).")

        # Detect flat sections / saturation
        diff_y = np.diff(y)
        flat_runs = []
        cur_run = 0
        for dy in diff_y:
            if abs(dy) < 1e-12:
                cur_run += 1
            else:
                if cur_run > 0:
                    flat_runs.append(cur_run)
                cur_run = 0
        if cur_run > 0:
            flat_runs.append(cur_run)

        longest_flat_samples = max(flat_runs) if flat_runs else 0
        longest_flat_dur_s = longest_flat_samples * med_dt if med_dt else 0.0
        if longest_flat_dur_s > 2.0:
            warnings.append(f"Detected long flat section of {longest_flat_samples} samples ({longest_flat_dur_s:.2f}s).")

        # Clipping estimation
        n_clipped = 0
        pct_clipped = 0.0
        if len(y) > 20:
            q_high = np.quantile(y, self.config.clipping_quantile_threshold)
            q_low = np.quantile(y, 1.0 - self.config.clipping_quantile_threshold)
            n_clipped = int(np.sum(y >= q_high) + np.sum(y <= q_low))
            pct_clipped = float(n_clipped / len(y) * 100.0)

        # 6. Final QC status
        if errors or is_const or n_valid < self.config.min_samples_per_trial:
            qc_status = "FAILED"
        elif warnings:
            qc_status = "WARNING"
        else:
            qc_status = "PASSED"

        report = SignalQualityReport(
            file_path=file_path,
            participant_id=participant_id,
            task=task,
            signal_selected=signal_col_used,
            signal_selection_reason=selection_reason,
            n_raw_samples=n_raw,
            n_valid_samples=n_valid,
            n_missing_samples=n_missing,
            pct_missing=pct_missing,
            n_duplicate_timestamps=n_dup,
            n_non_monotonic_timestamps=n_non_mono,
            time_span_s=t_span,
            median_dt_s=med_dt,
            std_dt_s=std_dt,
            cv_dt=cv_dt,
            estimated_fs_hz=est_fs,
            n_gaps=n_gaps,
            total_gap_duration_s=total_gap_dur,
            max_gap_duration_s=max_gap_dur,
            is_constant_signal=is_const,
            signal_variance=sig_var,
            signal_min=sig_min,
            signal_max=sig_max,
            signal_range=sig_range,
            n_clipped_samples=n_clipped,
            pct_clipped=pct_clipped,
            longest_flat_section_samples=longest_flat_samples,
            longest_flat_section_duration_s=longest_flat_dur_s,
            quality_status=qc_status,
            warnings=warnings,
            errors=errors,
        )

        clean_df = pd.DataFrame({
            "time": t,
            "signal": y,
            "raw_resistance": r_clean,
        })

        return clean_df, report

    def _create_empty_report(
        self,
        file_path: str,
        participant_id: str,
        task: str,
        errors: list[str],
        n_raw: int = 0,
        n_valid: int = 0,
    ) -> SignalQualityReport:
        return SignalQualityReport(
            file_path=file_path,
            participant_id=participant_id,
            task=task,
            signal_selected="NONE",
            signal_selection_reason="Failed validation",
            n_raw_samples=n_raw,
            n_valid_samples=n_valid,
            n_missing_samples=n_raw - n_valid,
            pct_missing=100.0,
            n_duplicate_timestamps=0,
            n_non_monotonic_timestamps=0,
            time_span_s=0.0,
            median_dt_s=np.nan,
            std_dt_s=np.nan,
            cv_dt=np.nan,
            estimated_fs_hz=np.nan,
            n_gaps=0,
            total_gap_duration_s=0.0,
            max_gap_duration_s=0.0,
            is_constant_signal=True,
            signal_variance=0.0,
            signal_min=np.nan,
            signal_max=np.nan,
            signal_range=0.0,
            n_clipped_samples=0,
            pct_clipped=0.0,
            longest_flat_section_samples=0,
            longest_flat_section_duration_s=0.0,
            quality_status="FAILED",
            warnings=[],
            errors=errors,
        )

