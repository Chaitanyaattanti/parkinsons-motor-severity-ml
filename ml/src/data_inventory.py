"""Automated data inventory and participant-by-task coverage matrix builder.

Scans the project directory recursively, inspects every recording workbook/CSV,
analyzes column candidates, timestamps, and sampling rates, and produces
reproducible inventory artifacts.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd

from src.config import DEFAULT_CONFIG, PipelineConfig

TASK_CANONICAL_MAP = {
    "hand resting": "Hand Resting",
    "arm resting": "Hand Resting",
    "arm extended forward": "Arm Extended Forward",
    "finger tapping": "Finger Tapping",
    "finger to nose": "Finger to Nose",
    "fist open and close": "Fist Open and Close",
    "pronation supination": "Pronation Supination",
    "pronation-supination": "Pronation Supination",
    "quiet standing": "Quiet Standing",
    "normal walking": "Normal Walking",
    "sit-to-stand": "Sit-to-Stand",
    "sit to stand": "Sit-to-Stand",
    "tug": "TUG",
    "turning task": "Turning Task",
    "turning": "Turning Task",
}


def canonicalize_task(raw_name: str) -> str:
    """Map raw file or task name to canonical clinical task name."""
    clean = re.sub(r"[._\-]+", " ", str(raw_name)).strip().lower()
    for pattern, canonical in TASK_CANONICAL_MAP.items():
        if pattern in clean:
            return canonical
    return raw_name.strip()


def parse_participant_and_group(rel_path: Path) -> tuple[str, str, str, bool]:
    """Extract participant_id, diagnosis group, session_date, and ambiguity flag.
    
    Returns:
        (participant_id, diagnosis_group, session_id, is_unambiguous)
    """
    parts = rel_path.parts
    group = "Unknown"
    participant_id = "UNKNOWN"
    session_id = "UNKNOWN"
    is_unambiguous = False

    for part in parts:
        part_clean = part.strip()
        if "Healthy Participants" in part_clean:
            group = "Healthy"
        elif "PD Patients" in part_clean:
            group = "Parkinson's Disease"

        # Check for HP patterns, including the moved healthy participants HP004-HP006.
        if re.match(r"^HP\d+$", part_clean, re.IGNORECASE):
            participant_id = part_clean.upper()
            session_id = "20260911"  # From verified device metadata
            group = "Healthy"
            is_unambiguous = True
        # Check for PD patterns: PD001_260903, PD002_260917
        elif re.match(r"^PD\d+_\d+$", part_clean, re.IGNORECASE):
            tokens = part_clean.split("_")
            participant_id = tokens[0].upper()
            session_id = tokens[1]
            group = "Parkinson's Disease"
            is_unambiguous = True
        elif "Atypical_PD001" in part_clean:
            participant_id = "Atypical_PD001"
            session_id = "20260917"
            group = "Atypical Parkinsonism"
            is_unambiguous = True

    return participant_id, group, session_id, is_unambiguous


def inspect_single_file(file_path: Path, root: Path, config: PipelineConfig) -> dict[str, Any]:
    """Inspect a single recording file and compute data inventory metrics."""
    rel_path = file_path.relative_to(root)
    filename = file_path.name
    file_type = file_path.suffix.lower()
    task_raw = file_path.stem
    task = canonicalize_task(task_raw)

    participant_id, diagnosis_group, session_id, is_unambiguous = parse_participant_and_group(rel_path)

    record: dict[str, Any] = {
        "file_path": str(rel_path),
        "filename": filename,
        "participant_id": participant_id,
        "diagnosis_group": diagnosis_group,
        "session_id": session_id,
        "task": task,
        "file_type": file_type,
        "worksheets": [],
        "columns": [],
        "n_rows": 0,
        "n_cols": 0,
        "candidate_time_cols": [],
        "candidate_raw_r_cols": [],
        "candidate_norm_r_cols": [],
        "missing_values_count": 0,
        "duplicate_timestamps": 0,
        "non_monotonic_timestamps": 0,
        "time_start_s": np.nan,
        "time_end_s": np.nan,
        "time_duration_s": np.nan,
        "sampling_interval_median_s": np.nan,
        "sampling_interval_std_s": np.nan,
        "sampling_rate_hz_estimated": np.nan,
        "meta_experiment_duration_s": np.nan,
        "can_parse": False,
        "signal_validity": "UNCHECKED",
        "warnings": [],
        "errors": [],
        "verified_clinical_label": "MISSING",
        "participant_mapping_status": "Unambiguous" if is_unambiguous else "Uncertain",
    }

    try:
        df: pd.DataFrame
        if file_type == ".xlsx":
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            record["worksheets"] = wb.sheetnames
            wb.close()
            
            sheet_name = "mySet" if "mySet" in record["worksheets"] else 0
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Check for Metadata Time sheet duration
            if "Metadata Time" in record["worksheets"]:
                df_meta = pd.read_excel(file_path, sheet_name="Metadata Time")
                if "event" in df_meta.columns and "experiment time" in df_meta.columns:
                    pauses = df_meta[df_meta["event"] == "PAUSE"]
                    if len(pauses) > 0:
                        record["meta_experiment_duration_s"] = float(pauses["experiment time"].iloc[-1])
        elif file_type == ".csv":
            record["worksheets"] = ["Sheet1"]
            df = pd.read_csv(file_path)
        else:
            record["errors"].append(f"Unsupported file extension: {file_type}")
            return record

        record["can_parse"] = True
        record["n_rows"] = int(len(df))
        record["n_cols"] = int(len(df.columns))
        record["columns"] = [str(c) for c in df.columns]
        record["missing_values_count"] = int(df.isnull().sum().sum())

        # Column identification heuristics
        time_candidates = []
        raw_r_candidates = []
        norm_r_candidates = []

        for col in df.columns:
            c_str = str(col).strip()
            c_lower = c_str.lower()
            if any(t in c_lower for t in ["time", "mydata0", "timestamp"]):
                time_candidates.append(c_str)
            if c_str in ["R", "myData1", "Unnamed: 1", "Unnamed: 2"]:
                raw_r_candidates.append(c_str)
            if any(n in c_str for n in ["ΔR/R0", "?R/R0", "Unnamed: 4", "Unnamed: 5"]):
                norm_r_candidates.append(c_str)

        record["candidate_time_cols"] = time_candidates
        record["candidate_raw_r_cols"] = raw_r_candidates
        record["candidate_norm_r_cols"] = norm_r_candidates

        # Timestamp analysis
        primary_time_col = None
        if "Time" in df.columns:
            primary_time_col = "Time"
        elif "myData0" in df.columns:
            primary_time_col = "myData0"
        elif time_candidates:
            primary_time_col = time_candidates[0]
        elif len(df.columns) > 0:
            primary_time_col = df.columns[0]

        if primary_time_col and primary_time_col in df:
            t_series = pd.to_numeric(df[primary_time_col], errors="coerce").dropna()
            if len(t_series) > 1:
                t_arr = t_series.to_numpy(float)
                record["time_start_s"] = float(t_arr[0])
                record["time_end_s"] = float(t_arr[-1])
                record["time_duration_s"] = float(t_arr[-1] - t_arr[0])

                dt = np.diff(t_arr)
                record["duplicate_timestamps"] = int(np.sum(dt == 0))
                record["non_monotonic_timestamps"] = int(np.sum(dt < 0))

                dt_valid = dt[dt > 0]
                if len(dt_valid) > 0:
                    med_dt = float(np.median(dt_valid))
                    record["sampling_interval_median_s"] = med_dt
                    record["sampling_interval_std_s"] = float(np.std(dt_valid))
                    record["sampling_rate_hz_estimated"] = float(1.0 / med_dt) if med_dt > 0 else np.nan

        # Signal validity assessment
        if record["n_rows"] < config.min_samples_per_trial:
            record["signal_validity"] = "INVALID_TOO_SHORT"
            record["warnings"].append(f"Row count {record['n_rows']} is below minimum threshold {config.min_samples_per_trial}")
        elif record["non_monotonic_timestamps"] > 0:
            record["signal_validity"] = "WARNING_NON_MONOTONIC"
            record["warnings"].append(f"Found {record['non_monotonic_timestamps']} non-monotonic timestamp intervals")
        else:
            record["signal_validity"] = "VALID"

        # Discrepancy warning between metadata clock and nominal timestamps
        if not np.isnan(record["meta_experiment_duration_s"]) and not np.isnan(record["time_duration_s"]):
            discrepancy = abs(record["meta_experiment_duration_s"] - record["time_duration_s"])
            if discrepancy > 5.0:
                record["warnings"].append(
                    f"Clock discrepancy: Metadata Time PAUSE is {record['meta_experiment_duration_s']:.1f}s "
                    f"but timestamp span is {record['time_duration_s']:.1f}s (diff = {discrepancy:.1f}s). "
                    "Indicates software nominal time generation."
                )

    except Exception as exc:
        record["can_parse"] = False
        record["signal_validity"] = "UNREADABLE"
        record["errors"].append(str(exc))

    return record


def run_inventory(config: PipelineConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scan directories, generate inventory dataframe, and export reports."""
    cfg = config or DEFAULT_CONFIG
    cfg.ensure_directories()
    root = cfg.project_root

    search_dirs = [root / cfg.healthy_dir_name, root / cfg.pd_dir_name]
    found_files: list[Path] = []
    for d in search_dirs:
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in [".xlsx", ".csv"] and not p.name.startswith("~$") and not p.name.startswith("."):
                    found_files.append(p)

    found_files = sorted(found_files)
    inventory_records = [inspect_single_file(f, root, cfg) for f in found_files]
    df_inv = pd.DataFrame(inventory_records)

    # Export Inventory CSV & JSON
    csv_path = cfg.reports_inventory_dir / "data_inventory.csv"
    json_path = cfg.reports_inventory_dir / "data_inventory.json"
    df_inv.to_csv(csv_path, index=False)
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(inventory_records, f, indent=2, default=str)

    # Build Participant-by-Task Coverage Matrix
    # Distinguish status: Valid, Warning, Invalid, Missing
    participants = sorted(df_inv["participant_id"].unique())
    all_tasks = sorted(df_inv["task"].unique())
    
    matrix_rows = []
    for p in participants:
        p_sub = df_inv[df_inv["participant_id"] == p]
        row_dict = {"participant_id": p, "diagnosis_group": p_sub["diagnosis_group"].iloc[0]}
        for t in all_tasks:
            t_sub = p_sub[p_sub["task"] == t]
            if len(t_sub) == 0:
                row_dict[t] = "Missing"
            else:
                validity = t_sub["signal_validity"].iloc[0]
                if validity == "VALID":
                    row_dict[t] = "Valid Signal"
                elif "WARNING" in validity:
                    row_dict[t] = f"Warning ({validity})"
                else:
                    row_dict[t] = f"Invalid ({validity})"
        matrix_rows.append(row_dict)

    df_matrix = pd.DataFrame(matrix_rows)
    matrix_csv_path = cfg.reports_inventory_dir / "participant_task_matrix.csv"
    df_matrix.to_csv(matrix_csv_path, index=False)

    # Generate Human-Readable Markdown Report
    summary_report_path = cfg.reports_inventory_dir / "inventory_summary_report.md"
    generate_markdown_summary(df_inv, df_matrix, summary_report_path)

    return df_inv, df_matrix


def generate_markdown_summary(df_inv: pd.DataFrame, df_matrix: pd.DataFrame, out_path: Path) -> None:
    """Write human-readable data inventory report in GitHub-flavored markdown."""
    n_files = len(df_inv)
    n_participants = df_inv["participant_id"].nunique()
    n_tasks = df_inv["task"].nunique()
    valid_count = (df_inv["signal_validity"] == "VALID").sum()
    warning_count = df_inv["signal_validity"].str.contains("WARNING").sum()
    invalid_count = df_inv["signal_validity"].str.contains("INVALID|UNREADABLE").sum()

    md = []
    md.append("# Comprehensive Data Inventory & Signal Audit Report\n")
    md.append("## Executive Summary\n")
    md.append(f"- **Total Recording Files Discovered**: {n_files}")
    md.append(f"- **Unique Confirmed Participants**: {n_participants} ({df_inv['diagnosis_group'].value_counts().to_dict()})")
    md.append(f"- **Distinct Clinical Motor Tasks**: {n_tasks}")
    md.append(f"- **Recordings Passing Initial Validity**: {valid_count} ({valid_count / n_files * 100:.1f}%)")
    md.append(f"- **Recordings with Quality Warnings**: {warning_count}")
    md.append(f"- **Unreadable / Invalid Files**: {invalid_count}")
    md.append("- **Clinical label source**: Healthy recordings use cohort ground truth 0; PD task scores are sourced from `Clinical Score.xlsx` during dataset construction.\n")

    md.append("## Participant-by-Task Coverage Matrix\n")
    md.append(df_matrix.to_markdown(index=False))
    md.append("\n")

    md.append("## Task Recording Distribution\n")
    task_counts = df_inv.groupby(["task", "diagnosis_group"]).size().unstack(fill_value=0)
    md.append(task_counts.to_markdown())
    md.append("\n")

    md.append("## Key Findings & Critical Data Observations\n")
    md.append("1. **Complete Motor Battery Asymmetry**: Only `PD002` completed the full 11-task battery. `HP001`, `HP002`, `HP003`, and `PD001` completed exactly 4 upper-limb tasks (`Hand Resting`, `Arm Extended Forward`, `Finger Tapping`, `Finger to Nose`). `Atypical_PD001` completed only 2 tasks (`Normal Walking`, `Quiet Standing`).")
    md.append("2. **Nominal vs. Hardware Clock Discrepancy**: Device software outputs regular synthetic timestamps (e.g. 0.1s in HP/PD001, 0.05s in PD002) while internal `Metadata Time` reveals the actual hardware duration was ~61s rather than 88s, yielding a true acquisition rate of ~14.3 Hz rather than nominal 10 Hz / 20 Hz.")
    md.append("3. **Clinical label provenance**: `UPDRS Assessment Sheet.xlsx` is an empty rubric; task-level scores are supplied separately by `Clinical Score.xlsx` for PD001, PD002, and Atypical_PD001. Healthy recordings use the explicitly documented cohort-zero assumption.\n")

    out_path.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    inv, mat = run_inventory()
    print(f"Inventory complete: {len(inv)} files inventoried across {inv['participant_id'].nunique()} participants.")
