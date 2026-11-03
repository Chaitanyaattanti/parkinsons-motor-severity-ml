"""Master dataset construction module for Parkinson's motor severity pipeline.

Builds recording-level, participant-task aggregated, and long-form feature datasets
while strictly preserving participant identity, missing data flags, and clinical label absence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pandas as pd

from src.common_features import extract_common_features
from src.config import DEFAULT_CONFIG, PipelineConfig
from src.data_inventory import canonicalize_task, parse_participant_and_group
from src.frequency_features import extract_frequency_features
from src.preprocessing import ProcessedSignal, SignalPreprocessor
from src.task_features import extract_task_specific_features

# Sensor locations based on clinical protocol workbook
TASK_SENSOR_LOCATIONS = {
    "Hand Resting": "Wrist/Forearm",
    "Arm Extended Forward": "Wrist/Forearm",
    "Finger Tapping": "Wrist/Index Finger",
    "Finger to Nose": "Wrist/Forearm",
    "Fist Open and Close": "Wrist/Forearm",
    "Pronation Supination": "Wrist/Forearm",
    "Quiet Standing": "Lower Limb/Shoe Insole",
    "Normal Walking": "Lower Limb/Shoe Insole",
    "Sit-to-Stand": "Lower Limb/Shoe Insole",
    "TUG": "Lower Limb/Shoe Insole",
    "Turning Task": "Lower Limb/Shoe Insole",
}


def build_master_datasets(config: PipelineConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Process all discovered recordings, extract all features, and construct master tables."""
    cfg = config or DEFAULT_CONFIG
    cfg.ensure_directories()
    root = cfg.project_root

    preprocessor = SignalPreprocessor(cfg)

    # 1. Discover all files
    search_dirs = [root / cfg.healthy_dir_name, root / cfg.pd_dir_name]
    found_files: list[Path] = []
    for d in search_dirs:
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in [".xlsx", ".csv"] and not p.name.startswith("~$") and not p.name.startswith("."):
                    found_files.append(p)

    found_files = sorted(found_files)

    recording_records: list[dict[str, Any]] = []
    quality_records: list[dict[str, Any]] = []
    long_form_records: list[dict[str, Any]] = []

    for idx, fpath in enumerate(found_files, 1):
        rel_path = fpath.relative_to(root)
        task = canonicalize_task(fpath.stem)
        participant_id, diagnosis_group, session_id, _ = parse_participant_and_group(rel_path)
        recording_id = f"REC_{participant_id}_{task.replace(' ', '_')}_{session_id}"

        # Load raw file
        if fpath.suffix.lower() == ".xlsx":
            wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
            sheet_name = "mySet" if "mySet" in wb.sheetnames else 0
            wb.close()
            df_raw = pd.read_excel(fpath, sheet_name=sheet_name)
        else:
            df_raw = pd.read_csv(fpath)

        # Preprocess signal
        proc: ProcessedSignal = preprocessor.process(
            df=df_raw,
            file_path=str(rel_path),
            participant_id=participant_id,
            task=task,
        )

        qc = proc.qc_report
        quality_records.append(qc.to_dict())

        # Extract features
        common_feats = extract_common_features(proc, cfg)
        freq_feats, freq_reasons = extract_frequency_features(proc, cfg)
        task_feats = extract_task_specific_features(proc, cfg)

        # Assemble master recording record
        rec_dict: dict[str, Any] = {
            "recording_id": recording_id,
            "participant_id": participant_id,
            "diagnosis": diagnosis_group,
            "session_id": session_id,
            "task": task,
            "file_path": str(rel_path),
            "file_type": fpath.suffix.lower(),
            "sensor_side": "Unspecified",
            "sensor_location": TASK_SENSOR_LOCATIONS.get(task, "Unspecified"),
            "signal_column_used": qc.signal_selected,
            "recording_duration_s": proc.duration_s,
            "sampling_rate_hz": proc.fs_effective,
            "quality_status": qc.quality_status,
            "quality_warnings": "; ".join(qc.warnings) if qc.warnings else "None",
            # Clinical label is strictly unassigned - NO fake labels
            "clinical_score": np.nan,
            "clinical_score_source": "Unresolved / None Available",
            "label_verified": False,
        }

        # Merge feature dictionaries
        all_feats = {**common_feats, **freq_feats, **task_feats}
        rec_dict.update(all_feats)
        recording_records.append(rec_dict)

        # Long form entries
        for f_name, f_val in all_feats.items():
            long_form_records.append({
                "recording_id": recording_id,
                "participant_id": participant_id,
                "diagnosis": diagnosis_group,
                "task": task,
                "feature_name": f_name,
                "feature_value": f_val,
            })

    # --- Table A: Recording-Level Feature Table ---
    df_rec = pd.DataFrame(recording_records)
    rec_csv_path = cfg.features_dir / "recording_level_features.csv"
    df_rec.to_csv(rec_csv_path, index=False)

    # --- Table B: Participant-Task Aggregated Table ---
    # Aggregate across repeated trials for same participant and task (if any)
    id_cols = ["participant_id", "diagnosis", "task"]
    feat_cols = [c for c in df_rec.columns if c not in [
        "recording_id", "participant_id", "diagnosis", "session_id", "task",
        "file_path", "file_type", "sensor_side", "sensor_location",
        "signal_column_used", "quality_status", "quality_warnings",
        "clinical_score", "clinical_score_source", "label_verified"
    ]]

    # Numeric aggregation
    df_part_task = df_rec.groupby(id_cols, dropna=False)[feat_cols].agg(["mean", "std", "count"])
    df_part_task.columns = [f"{col}_{stat}" for col, stat in df_part_task.columns]
    df_part_task = df_part_task.reset_index()

    # Add clinical score placeholders
    df_part_task["clinical_score"] = np.nan
    df_part_task["clinical_score_source"] = "Unresolved / None Available"
    df_part_task["label_verified"] = False

    part_task_csv_path = cfg.features_dir / "participant_task_features.csv"
    df_part_task.to_csv(part_task_csv_path, index=False)

    # --- Table C: Long-Form Feature Table ---
    df_long = pd.DataFrame(long_form_records)
    long_csv_path = cfg.features_dir / "long_form_features.csv"
    df_long.to_csv(long_csv_path, index=False)

    # Save Quality Control Report
    df_qc = pd.DataFrame(quality_records)
    qc_csv_path = cfg.reports_quality_dir / "signal_quality_report.csv"
    df_qc.to_csv(qc_csv_path, index=False)

    return df_rec, df_part_task, df_long


if __name__ == "__main__":
    r, pt, l = build_master_datasets()
    print(f"Master datasets constructed:")
    print(f"  Recording-level: {r.shape[0]} rows, {r.shape[1]} columns")
    print(f"  Participant-task: {pt.shape[0]} rows, {pt.shape[1]} columns")
    print(f"  Long-form: {l.shape[0]} rows")

