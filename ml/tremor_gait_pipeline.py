"""Train patient-level tremor/gait models from pressure trials and ratings.

Expected pressure CSV columns:
patient_id, session_id, trial_id, timestamp, pressure
Optional columns: task, sensor_id, side, sensor_location.

Expected ratings CSV is either wide (one row per patient/session with columns
such as gait_walking_score) or long with columns:
patient_id, session_id, rating_system, rating_item, score.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, periodogram
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ID_COLUMNS = ["patient_id", "session_id"]
REQUIRED_SENSOR_COLUMNS = ID_COLUMNS + ["trial_id", "timestamp", "pressure"]


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _numeric_signal(frame: pd.DataFrame) -> np.ndarray:
    values = pd.to_numeric(frame["pressure"], errors="coerce").dropna().to_numpy(float)
    if values.size < 4:
        raise ValueError("Each trial needs at least four numeric pressure samples.")
    return values


def _sampling_rate(frame: pd.DataFrame) -> float:
    times = pd.to_numeric(frame["timestamp"], errors="coerce").dropna().to_numpy(float)
    diffs = np.diff(times)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if not diffs.size:
        raise ValueError("Timestamp must be numeric and strictly increasing within a trial.")
    return float(1.0 / np.median(diffs))


def _signal_features(signal: np.ndarray, sample_rate: float, prefix: str = "") -> dict[str, float]:
    centered = signal - np.mean(signal)
    frequencies, powers = periodogram(centered, fs=sample_rate)
    nonzero = frequencies > 0
    dominant_frequency = float(frequencies[nonzero][np.argmax(powers[nonzero])]) if nonzero.any() else 0.0
    peak_count = len(find_peaks(centered, prominence=max(np.std(centered) * 0.5, 1e-12), distance=max(1, int(sample_rate * 0.2)))[0])
    return {
        f"{prefix}mean_pressure": float(np.mean(signal)),
        f"{prefix}std_pressure": float(np.std(signal)),
        f"{prefix}rms_pressure": float(np.sqrt(np.mean(signal**2))),
        f"{prefix}peak_pressure": float(np.max(signal)),
        f"{prefix}range_pressure": float(np.ptp(signal)),
        f"{prefix}dominant_frequency_hz": dominant_frequency,
        f"{prefix}spectral_energy": float(np.sum(powers[nonzero])),
        f"{prefix}peak_count": float(peak_count),
    }


def _gait_features(signal: np.ndarray, sample_rate: float) -> dict[str, float]:
    threshold = np.mean(signal) + 0.2 * np.std(signal)
    contacts = np.flatnonzero((signal[:-1] <= threshold) & (signal[1:] > threshold)) + 1
    intervals = np.diff(contacts) / sample_rate
    intervals = intervals[intervals > 0]
    return {
        "step_count": float(len(contacts)),
        "step_time_mean_s": float(np.mean(intervals)) if intervals.size else np.nan,
        "step_time_std_s": float(np.std(intervals)) if intervals.size else np.nan,
        "cadence_steps_per_min": float(60 / np.mean(intervals)) if intervals.size else np.nan,
    }


def extract_trial_features(sensor: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_SENSOR_COLUMNS) - set(sensor.columns)
    if missing:
        raise ValueError(f"Sensor CSV is missing required columns: {sorted(missing)}")

    records: list[dict[str, object]] = []
    group_columns = ID_COLUMNS + ["trial_id"]
    for keys, trial in sensor.groupby(group_columns, dropna=False):
        trial = trial.sort_values("timestamp")
        signal = _numeric_signal(trial)
        sample_rate = _sampling_rate(trial)
        record = dict(zip(group_columns, keys))
        record["task"] = str(trial["task"].iloc[0]) if "task" in trial else "unspecified"
        record["duration_s"] = float(pd.to_numeric(trial["timestamp"]).max() - pd.to_numeric(trial["timestamp"]).min())
        record.update(_signal_features(signal, sample_rate))
        task = _slug(record["task"])
        if any(term in task for term in ("walk", "gait", "turn", "tug", "standing")):
            record.update(_gait_features(signal, sample_rate))
        if "sensor_id" in trial and trial["sensor_id"].nunique() > 1:
            per_sensor = trial.groupby("sensor_id", dropna=False)
            rms_values = []
            for _, sensor_trial in per_sensor:
                sensor_signal = _numeric_signal(sensor_trial)
                rms_values.append(np.sqrt(np.mean(sensor_signal**2)))
            record["sensor_rms_mean"] = float(np.mean(rms_values))
            record["sensor_rms_std"] = float(np.std(rms_values))
        records.append(record)
    if not records:
        raise ValueError("No valid pressure trials were found.")
    return pd.DataFrame(records)


def aggregate_patient_features(trial_features: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = trial_features.select_dtypes(include=np.number).columns.tolist()
    aggregations = {column: ["mean", "std", "median"] for column in numeric_columns if column not in ID_COLUMNS}
    result = trial_features.groupby(ID_COLUMNS, dropna=False).agg(aggregations)
    result.columns = [f"{column}_{stat}" for column, stat in result.columns]
    return result.reset_index()


def load_ratings(path: str | Path) -> pd.DataFrame:
    ratings = pd.read_csv(path)
    required_ids = set(ID_COLUMNS)
    if not required_ids.issubset(ratings.columns):
        raise ValueError(f"Ratings CSV must contain {sorted(required_ids)}.")
    long_columns = {"rating_system", "rating_item", "score"}
    if long_columns.issubset(ratings.columns):
        ratings = ratings.copy()
        ratings["target"] = ratings.apply(
            lambda row: f"{_slug(row.rating_system)}_{_slug(row.rating_item)}_score", axis=1
        )
        ratings = ratings.pivot_table(index=ID_COLUMNS, columns="target", values="score", aggfunc="mean").reset_index()
        ratings.columns.name = None
    return ratings


def _models() -> dict[str, Pipeline]:
    return {
        "ridge": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]),
        "random_forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42, n_jobs=-1)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingRegressor(max_iter=150, l2_regularization=1.0, random_state=42)),
        ]),
    }


def train(sensor_csv: str | Path, ratings_csv: str | Path, target: str, output_dir: str | Path) -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    trials = extract_trial_features(pd.read_csv(sensor_csv))
    features = aggregate_patient_features(trials)
    ratings = load_ratings(ratings_csv)
    if target not in ratings.columns:
        available = sorted(column for column in ratings.columns if column not in ID_COLUMNS)
        raise ValueError(f"Target {target!r} was not found. Available rating columns: {available}")
    dataset = features.merge(ratings[ID_COLUMNS + [target]], on=ID_COLUMNS, how="inner")
    dataset[target] = pd.to_numeric(dataset[target], errors="coerce")
    dataset = dataset.dropna(subset=[target])
    if dataset["patient_id"].nunique() < 3:
        raise ValueError("At least three distinct patients are required for patient-group validation.")
    feature_columns = [column for column in features.columns if column not in ID_COLUMNS]
    x = dataset[feature_columns]
    y = dataset[target].to_numpy(float)
    groups = dataset["patient_id"]
    n_splits = min(5, groups.nunique())
    cv = GroupKFold(n_splits=n_splits)
    scores: dict[str, dict[str, float]] = {}
    predictions: dict[str, np.ndarray] = {}
    for name, model in _models().items():
        predicted = cross_val_predict(model, x, y, cv=cv, groups=groups)
        predictions[name] = predicted
        scores[name] = {
            "mae": float(mean_absolute_error(y, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(y, predicted))),
            "r2": float(r2_score(y, predicted)) if len(np.unique(y)) > 1 else float("nan"),
        }
    best_name = min(scores, key=lambda name: scores[name]["mae"])
    best_model = _models()[best_name].fit(x, y)
    joblib.dump({"model": best_model, "features": feature_columns, "target": target}, output / "model.joblib")
    trials.to_csv(output / "trial_features.csv", index=False)
    dataset.to_csv(output / "training_dataset.csv", index=False)
    pd.DataFrame({"patient_id": dataset.patient_id, "session_id": dataset.session_id, "actual": y, "predicted": predictions[best_name]}).to_csv(output / "oof_predictions.csv", index=False)
    (output / "metrics.json").write_text(json.dumps({"target": target, "selected_model": best_name, "n_patients": int(groups.nunique()), "n_sessions": int(len(dataset)), "models": scores}, indent=2))
    return {"selected_model": best_name, "scores": scores, "n_patients": int(groups.nunique()), "n_sessions": int(len(dataset))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensor-csv", required=True)
    parser.add_argument("--ratings-csv", required=True)
    parser.add_argument("--target", required=True, help="Rating column, for example updrs_walking_score")
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()
    print(json.dumps(train(args.sensor_csv, args.ratings_csv, args.target, args.output_dir), indent=2))


if __name__ == "__main__":
    main()