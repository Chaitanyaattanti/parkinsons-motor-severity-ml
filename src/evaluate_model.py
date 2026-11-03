"""Evaluation metrics and model performance reporting module.

Computes clinical regression metrics (MAE, RMSE, Pearson r, valid range compliance)
and ordinal classification metrics (Macro-F1, accuracy, ordinal confusion matrix).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score


def evaluate_regression_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    clip_to_valid_range: bool = True,
) -> dict[str, float]:
    """Calculate clinically relevant regression metrics for motor severity estimation."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) == 0:
        return {
            "mae": np.nan,
            "rmse": np.nan,
            "pearson_r": np.nan,
            "r2": np.nan,
            "pct_in_range_0_to_4": np.nan,
        }

    # Range compliance before clipping
    in_range = (y_pred >= 0.0) & (y_pred <= 4.0)
    pct_in_range = float(np.mean(in_range) * 100.0)

    if clip_to_valid_range:
        y_pred_eval = np.clip(y_pred, 0.0, 4.0)
    else:
        y_pred_eval = y_pred

    mae = float(mean_absolute_error(y_true, y_pred_eval))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred_eval)))

    # Pearson r if variance is non-zero
    if np.var(y_true) > 1e-12 and np.var(y_pred_eval) > 1e-12 and len(y_true) >= 3:
        r_val, _ = pearsonr(y_true, y_pred_eval)
        r_val = float(r_val)
    else:
        r_val = np.nan

    # R2 score
    if np.var(y_true) > 1e-12 and len(y_true) >= 2:
        r2 = float(r2_score(y_true, y_pred_eval))
    else:
        r2 = np.nan

    return {
        "mae": mae,
        "rmse": rmse,
        "pearson_r": r_val,
        "r2": r2,
        "pct_in_range_0_to_4": pct_in_range,
    }


def evaluate_ordinal_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Calculate ordinal classification metrics (Accuracy, Macro-F1, MAE as ordinal distance)."""
    y_true_round = np.round(np.clip(y_true, 0, 4)).astype(int)
    y_pred_round = np.round(np.clip(y_pred, 0, 4)).astype(int)

    acc = float(accuracy_score(y_true_round, y_pred_round))
    # Macro F1
    macro_f1 = float(f1_score(y_true_round, y_pred_round, average="macro", zero_division=0))
    # Ordinal MAE
    ord_mae = float(mean_absolute_error(y_true_round, y_pred_round))

    # Confusion matrix
    classes = [0, 1, 2, 3, 4]
    cm = pd.crosstab(
        pd.Series(y_true_round, name="Actual"),
        pd.Series(y_pred_round, name="Predicted"),
        dropna=False,
    ).reindex(index=classes, columns=classes, fill_value=0)

    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "ordinal_mae": ord_mae,
        "confusion_matrix": cm.to_dict(),
    }


def save_model_comparison_report(
    results: dict[str, Any],
    out_path: Path,
) -> None:
    """Save markdown comparison report of evaluated models."""
    md = []
    md.append("# Model Training & Grouped Evaluation Comparison Report\n")
    md.append(f"- **Target Score**: {results.get('target', 'MDS-UPDRS Motor Severity (0-4)')}")
    md.append(f"- **Status**: {results.get('status', 'EVALUATED')}")
    md.append(f"- **Number of Participants**: {results.get('n_participants', 0)}")
    md.append(f"- **Number of Recordings**: {results.get('n_recordings', 0)}")
    md.append(f"- **Validation Scheme**: {results.get('validation_scheme', 'GroupKFold / Leave-One-Participant-Out')}\n")

    if "models" in results:
        md.append("## Cross-Validation Performance Summary\n")
        table_rows = []
        for m_name, m_metrics in results["models"].items():
            table_rows.append({
                "Model": m_name,
                "MAE": round(m_metrics.get("mae", np.nan), 3),
                "RMSE": round(m_metrics.get("rmse", np.nan), 3),
                "Pearson r": round(m_metrics.get("pearson_r", np.nan), 3),
                "% In Valid Range [0, 4]": round(m_metrics.get("pct_in_range_0_to_4", np.nan), 1),
            })
        md.append(pd.DataFrame(table_rows).to_markdown(index=False))
        md.append("\n")

    if "warnings" in results and results["warnings"]:
        md.append("## Methodological Warnings & Limitations\n")
        for w in results["warnings"]:
            md.append(f"- {w}")
        md.append("\n")

    out_path.write_text("\n".join(md), encoding="utf-8")

