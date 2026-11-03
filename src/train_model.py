"""Supervised model training and participant-grouped evaluation harness.

Implements leakage-proof feature selection, median imputation, standardization,
grouped cross-validation by participant_id, baseline comparison, and strict
label-readiness auditing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.evaluate_model import evaluate_ordinal_predictions, evaluate_regression_predictions, save_model_comparison_report

# Columns that MUST be excluded from the feature predictor matrix to prevent leakage
NON_PREDICTIVE_COLUMNS = [
    "recording_id",
    "participant_id",
    "diagnosis",
    "session_id",
    "task",
    "file_path",
    "file_type",
    "sensor_side",
    "sensor_location",
    "signal_column_used",
    "quality_status",
    "quality_warnings",
    "clinical_score",
    "clinical_score_source",
    "label_verified",
    "recording_duration_s",
    "sampling_rate_hz",
]


def check_model_readiness(
    df: pd.DataFrame,
    target_column: str = "clinical_score",
) -> dict[str, Any]:
    """Audit whether the dataset possesses adequate verified clinical labels for ML."""
    if target_column not in df.columns:
        return {
            "ready": False,
            "status": "BLOCKED_TARGET_COLUMN_MISSING",
            "n_labeled_participants": 0,
            "n_labeled_rows": 0,
            "unique_score_values": [],
            "reason": f"Target column {target_column!r} not found in dataset.",
        }

    y_series = pd.to_numeric(df[target_column], errors="coerce").dropna()
    n_labeled = len(y_series)
    
    if n_labeled == 0:
        return {
            "ready": False,
            "status": "BLOCKED_NO_LABELS",
            "n_labeled_participants": 0,
            "n_labeled_rows": 0,
            "unique_score_values": [],
            "reason": (
                "Zero verified clinical scores (0-4) are available in the workspace. "
                "Per research specifications, scores cannot be fabricated or inferred from diagnosis."
            ),
        }

    valid_df = df.loc[y_series.index]
    n_participants = valid_df["participant_id"].nunique()
    unique_vals = sorted(y_series.unique().tolist())

    if n_participants < 3:
        return {
            "ready": False,
            "status": "BLOCKED_INSUFFICIENT_PARTICIPANTS",
            "n_labeled_participants": n_participants,
            "n_labeled_rows": n_labeled,
            "unique_score_values": unique_vals,
            "reason": f"At least 3 distinct participants are required for grouped validation; found {n_participants}.",
        }

    return {
        "ready": True,
        "status": "READY",
        "n_labeled_participants": n_participants,
        "n_labeled_rows": n_labeled,
        "unique_score_values": unique_vals,
        "reason": "Adequate labeled participants available for grouped evaluation.",
    }


def build_models() -> dict[str, Pipeline]:
    """Construct baseline and machine learning model pipelines."""
    return {
        "dummy_mean": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", DummyRegressor(strategy="mean")),
        ]),
        "dummy_median": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", DummyRegressor(strategy="median")),
        ]),
        "ridge_regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("variance_filter", VarianceThreshold(threshold=1e-8)),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0, random_state=42)),
        ]),
        "random_forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("variance_filter", VarianceThreshold(threshold=1e-8)),
            ("model", RandomForestRegressor(
                n_estimators=100,
                max_depth=3,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            )),
        ]),
    }


def train_and_evaluate_grouped(
    df: pd.DataFrame,
    target_column: str = "clinical_score",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Train models using strict participant-grouped cross-validation without leakage."""
    readiness = check_model_readiness(df, target_column)
    if not readiness["ready"]:
        raise ValueError(f"Cannot perform supervised evaluation: {readiness['reason']}")

    valid_df = df.dropna(subset=[target_column]).copy()
    valid_df[target_column] = pd.to_numeric(valid_df[target_column], errors="coerce")
    valid_df = valid_df.dropna(subset=[target_column])

    # Feature column selection: numeric columns excluding non-predictive metadata
    candidate_features = [
        c for c in valid_df.columns
        if c not in NON_PREDICTIVE_COLUMNS and c != target_column
    ]
    numeric_features = valid_df[candidate_features].select_dtypes(include=[np.number]).columns.tolist()

    x = valid_df[numeric_features]
    y = valid_df[target_column].to_numpy(float)
    groups = valid_df["participant_id"].to_numpy()

    n_groups = len(np.unique(groups))
    n_splits = min(5, n_groups)

    # Use GroupKFold or LeaveOneGroupOut
    if n_groups <= 5:
        cv = LeaveOneGroupOut()
    else:
        cv = GroupKFold(n_splits=n_splits)

    models = build_models()
    scores: dict[str, Any] = {}
    oof_predictions: dict[str, np.ndarray] = {}

    for name, pipeline in models.items():
        oof_preds = np.zeros(len(y), dtype=float)

        for train_idx, val_idx in cv.split(x, y, groups=groups):
            # Assert no participant overlap between train and test
            train_participants = set(groups[train_idx])
            val_participants = set(groups[val_idx])
            assert train_participants.isdisjoint(val_participants), "LEAKAGE DETECTED: Participant overlap across folds!"

            x_train, y_train = x.iloc[train_idx], y[train_idx]
            x_val = x.iloc[val_idx]

            # Fit pipeline strictly on training fold
            pipeline.fit(x_train, y_train)
            val_pred = pipeline.predict(x_val)
            oof_preds[val_idx] = val_pred

        oof_predictions[name] = oof_preds
        # Evaluate
        reg_metrics = evaluate_regression_predictions(y, oof_preds, clip_to_valid_range=True)
        ord_metrics = evaluate_ordinal_predictions(y, oof_preds)
        scores[name] = {**reg_metrics, **ord_metrics}

    # Best model selection by lowest MAE
    best_name = min(scores, key=lambda m: scores[m]["mae"])

    # Fit best model on entire labeled set for persistent artifact
    best_pipeline = build_models()[best_name]
    best_pipeline.fit(x, y)

    results = {
        "status": "SUCCESS",
        "target": target_column,
        "n_participants": int(n_groups),
        "n_recordings": int(len(valid_df)),
        "n_features_used": len(numeric_features),
        "features": numeric_features,
        "selected_model": best_name,
        "models": scores,
        "warnings": [
            f"Small sample size (N={n_groups} participants). Results have high uncertainty.",
            "Grouped cross-validation was strictly maintained by participant_id.",
        ],
    }

    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": best_pipeline, "features": numeric_features, "target": target_column}, out_p / "best_model.joblib")
        (out_p / "metrics.json").write_text(json.dumps(results, indent=2, default=str))

        # Save out-of-fold predictions
        oof_df = valid_df[["participant_id", "task"]].copy()
        oof_df["actual"] = y
        oof_df["predicted_score"] = oof_predictions[best_name]
        oof_df.to_csv(out_p / "oof_predictions.csv", index=False)

        save_model_comparison_report(results, out_p / "model_comparison_report.md")

    return results


def run_synthetic_integration_test(config: PipelineConfig | None = None) -> dict[str, Any]:
    """Execute complete grouped ML pipeline on synthetic mock data to verify zero leakage.
    
    IMPORTANT: This is solely a software integration test for unit verification.
    These synthetic metrics are NEVER reported as real clinical study findings.
    """
    cfg = config or DEFAULT_CONFIG
    cfg.ensure_directories()
    out_dir = cfg.reports_model_dir

    # Generate synthetic mock participant feature rows
    # 6 mock participants (3 healthy-like score 0, 3 PD-like scores 1, 2, 3)
    np.random.seed(cfg.random_state)
    mock_rows = []
    participants = ["MOCK_P01", "MOCK_P02", "MOCK_P03", "MOCK_P04", "MOCK_P05", "MOCK_P06"]
    mock_scores = {"MOCK_P01": 0.0, "MOCK_P02": 0.0, "MOCK_P03": 0.0, "MOCK_P04": 1.0, "MOCK_P05": 2.0, "MOCK_P06": 3.0}

    for p in participants:
        for t in ["Hand Resting", "Finger Tapping", "Finger to Nose", "Arm Extended Forward"]:
            score = mock_scores[p]
            mock_rows.append({
                "participant_id": p,
                "diagnosis": "Healthy" if score == 0 else "PD",
                "task": t,
                "signal_mean": float(np.random.normal(0.0, 0.01)),
                "signal_std": float(np.random.normal(0.01 * (score + 1), 0.002)),
                "signal_rms": float(np.random.normal(0.015 * (score + 1), 0.003)),
                "signal_range": float(np.random.normal(0.05 * (score + 1), 0.01)),
                "diff_abs_mean": float(np.random.normal(0.002 * (score + 1), 0.0005)),
                "total_variation": float(np.random.normal(0.2 * (score + 1), 0.05)),
                "peak_rate_per_sec": float(np.random.normal(1.5 + 0.5 * score, 0.2)),
                "dominant_frequency_hz": float(np.random.normal(3.5, 0.5)),
                "spectral_entropy": float(np.random.normal(0.8, 0.05)),
                "band_power_parkinsonian_3_0_to_5_0_hz": float(np.random.normal(0.001 * score, 0.0002)),
                "clinical_score": score,
            })

    df_mock = pd.DataFrame(mock_rows)
    test_results = train_and_evaluate_grouped(
        df=df_mock,
        target_column="clinical_score",
        output_dir=out_dir / "synthetic_test_harness",
    )

    test_report_path = out_dir / "synthetic_test_harness_report.md"
    md = []
    md.append("# Synthetic Mock Integration Test Verification Report\n")
    md.append("> [!NOTE]\n> **Software Verification Only: Never Construe as Clinical Findings**")
    md.append("This report documents the verification of the machine-learning pipeline using synthetic mock participants. It confirms that preprocessing, imputation, scaling, and GroupKFold cross-validation operate without leakage.\n")
    md.append(f"- **Best Model**: {test_results['selected_model']}")
    md.append(f"- **MAE**: {test_results['models'][test_results['selected_model']]['mae']:.3f}")
    md.append(f"- **RMSE**: {test_results['models'][test_results['selected_model']]['rmse']:.3f}")
    md.append(f"- **Participant Leakage Check**: PASSED (100% disjoint groups across all folds)\n")

    test_report_path.write_text("\n".join(md), encoding="utf-8")
    return test_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Parkinson's motor severity models")
    parser.add_argument("--features-csv", default="data/features/recording_level_features.csv")
    parser.add_argument("--ratings-csv", default=None, help="Optional external clinical ratings CSV")
    parser.add_argument("--target", default="clinical_score", help="Clinical target score column (0-4)")
    parser.add_argument("--output-dir", default="reports/model")
    parser.add_argument("--run-synthetic-test", action="store_true", help="Run synthetic integration test")
    args = parser.parse_args()

    cfg = DEFAULT_CONFIG
    cfg.ensure_directories()

    df_feats = pd.read_csv(args.features_csv)

    # Check model readiness on real data
    readiness = check_model_readiness(df_feats, args.target)

    audit_md_path = Path(args.output_dir) / "model_readiness_audit.md"
    audit_text = [
        "# Supervised Model Readiness Audit Report\n",
        f"- **Dataset Evaluated**: `{args.features_csv}`",
        f"- **Target Column Evaluated**: `{args.target}`",
        f"- **Supervised Model Training Readiness**: **{'READY' if readiness['ready'] else 'BLOCKED'}**",
        f"- **Status Code**: `{readiness['status']}`",
        f"- **Labeled Participants Found**: {readiness['n_labeled_participants']}",
        f"- **Labeled Recordings Found**: {readiness['n_labeled_rows']}",
        f"- **Detailed Reason**: {readiness['reason']}\n",
        "## Required Actions to Unblock Supervised ML",
        "1. Populate `reports/labels/label_mapping_template.csv` with real MDS-UPDRS Part III clinician scores (0-4).",
        "2. Ensure assessment dates match recording dates.",
        "3. Rerun pipeline with `--ratings-csv reports/labels/label_mapping_template.csv`.\n",
    ]
    audit_md_path.write_text("\n".join(audit_text), encoding="utf-8")
    print(f"Readiness audit written to {audit_md_path}: {readiness['status']}")

    # Always verify pipeline harness via synthetic integration test
    print("Running synthetic integration test to verify pipeline execution and leakage prevention...")
    synthetic_res = run_synthetic_integration_test(cfg)
    print(f"Synthetic test complete. Best model: {synthetic_res['selected_model']} (MAE: {synthetic_res['models'][synthetic_res['selected_model']]['mae']:.3f})")


if __name__ == "__main__":
    main()

