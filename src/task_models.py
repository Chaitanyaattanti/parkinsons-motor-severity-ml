"""Task-specific specialized model training module.

Trains and evaluates dedicated clinical models tailored to specific motor tasks
(e.g., Hand Resting Model for MDS-UPDRS 3.17, Finger Tapping Model for MDS-UPDRS 3.4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.evaluate_model import evaluate_ordinal_predictions, evaluate_regression_predictions
from src.ordinal_classifier import OrdinalThresholdRegressor
from src.train_model import NON_PREDICTIVE_COLUMNS, check_model_readiness

# Key feature subsets selected per task domain
TASK_FEATURE_PRIORITIES = {
    "Hand Resting": [
        "signal_std", "signal_rms", "signal_range", "diff_abs_mean", "total_variation",
        "peak_rate_per_sec", "peak_prominence_mean", "dominant_frequency_hz",
        "band_power_parkinsonian_3_0_to_5_0_hz", "tremor_power_ratio",
        "resting_amplitude_variability", "resting_rms", "resting_peak_prominence",
    ],
    "Finger Tapping": [
        "signal_std", "diff_abs_mean", "total_variation", "peak_rate_per_sec",
        "tap_count", "tap_rate_hz", "tap_interval_mean_s", "tap_interval_cv",
        "tap_amplitude_mean", "tap_amplitude_decrement_slope",
    ],
    "Arm Extended Forward": [
        "signal_std", "signal_rms", "diff_abs_mean", "total_variation",
        "postural_drift_slope", "postural_fatigue_ratio", "spectral_entropy",
        "dominant_frequency_hz", "band_power_parkinsonian_3_0_to_5_0_hz",
    ],
}


def train_task_specific_model(
    df: pd.DataFrame,
    task_name: str,
    target_column: str = "clinical_score",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Train a specialized model for a single motor task using domain-selected features."""
    task_df = df[df["task"] == task_name].dropna(subset=[target_column]).copy()
    readiness = check_model_readiness(task_df, target_column)
    if not readiness["ready"]:
        return {
            "task": task_name,
            "status": readiness["status"],
            "reason": readiness["reason"],
            "n_participants": readiness["n_labeled_participants"],
        }

    # Select prioritized features present in dataframe
    priority_cols = TASK_FEATURE_PRIORITIES.get(task_name, [])
    feat_cols = [c for c in priority_cols if c in task_df.columns]
    if not feat_cols:
        feat_cols = [
            c for c in task_df.select_dtypes(include=[np.number]).columns
            if c not in NON_PREDICTIVE_COLUMNS and c != target_column
        ]

    x = task_df[feat_cols]
    y = task_df[target_column].to_numpy(float)
    groups = task_df["participant_id"].to_numpy()

    # Leave-One-Participant-Out CV
    cv = LeaveOneGroupOut()
    oof_continuous = np.zeros(len(y), dtype=float)
    oof_ordinal = np.zeros(len(y), dtype=int)

    base_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("variance", VarianceThreshold(threshold=1e-8)),
        ("scaler", StandardScaler()),
        ("model", Ridge(alpha=1.0, random_state=42)),
    ])
    model = OrdinalThresholdRegressor(base_pipe)

    for train_idx, val_idx in cv.split(x, y, groups=groups):
        x_tr, y_tr = x.iloc[train_idx], y[train_idx]
        x_val = x.iloc[val_idx]

        model.fit(x_tr, y_tr)
        oof_continuous[val_idx] = model.predict_continuous(x_val)
        oof_ordinal[val_idx] = model.predict(x_val)

    reg_metrics = evaluate_regression_predictions(y, oof_continuous)
    ord_metrics = evaluate_ordinal_predictions(y, oof_ordinal)

    results = {
        "task": task_name,
        "status": "SUCCESS",
        "target": target_column,
        "n_participants": int(len(np.unique(groups))),
        "n_recordings": int(len(task_df)),
        "features_used": feat_cols,
        "metrics": {**reg_metrics, **ord_metrics},
    }

    if output_dir:
        out_p = Path(output_dir) / task_name.replace(" ", "_")
        out_p.mkdir(parents=True, exist_ok=True)
        (out_p / "task_metrics.json").write_text(json.dumps(results, indent=2, default=str))

    return results

