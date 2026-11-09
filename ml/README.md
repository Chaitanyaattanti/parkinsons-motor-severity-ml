# Parkinson's Motor Severity: Training and Machine Learning

This repository contains an exploratory pipeline for relating wearable resistance-sensor recordings to clinician-provided motor scores. The current scientific target is a 0–4 score for task-level motor severity, using the supplied clinical workbook and extracted recording-level features.

> **Status:** exploratory research only. The current dataset is too small for clinical validation or deployment.

## 1. End-to-end flow

```text
Raw Excel recordings
        ↓
Data inventory and signal validation
        ↓
Signal cleaning and quality checks
        ↓
Window/time-series processing
        ↓
Recording-level feature extraction
        ↓
Clinician score mapping
        ↓
Participant-held-out training and testing
        ↓
Metrics, predictions, and limitations
```

The notebook [clinical_score_training.ipynb](./clinical_score_training.ipynb) is retained as historical exploratory work. The current reproducible workflow is [src/pipeline.py](./src/pipeline.py).

## 2. Data and labels

The current generated feature table is `data/features/recording_level_features.csv`. It contains 50 recordings from 9 participants:

- 33 healthy recordings across HP001–HP006
- 15 Parkinson's disease recordings
- 2 atypical parkinsonism recordings

The supplied `Clinical Score.xlsx` provides task-level Part III scores for the three unhealthy participants. Healthy recordings use the explicitly documented cohort ground-truth score of 0.

| Group | Participants |
|---|---:|
| Healthy participants | 6 |
| Parkinson's disease participants | 2 |
| Atypical parkinsonism participants | 1 |
| Task-level labels available | 50 |

The workbook uses the project's earlier custom 33-item score structure. It is not automatically equivalent to the official MDS-UPDRS 3.1–3.18/33-element structure. The pipeline therefore uses an explicit, exploratory task-to-score mapping and documents that limitation.

Healthy recordings use the study cohort ground truth of 0 and are included with the workbook-derived Parkinsonian task scores in the combined evaluation dataset. This is a cohort-labeling assumption, not a substitute for an individual clinician UPDRS examination.

## 3. Feature extraction

The pipeline extracts numeric features from each recording, including:

- signal level, range, RMS, variability, skewness, and kurtosis
- first/second differences, jerk proxies, and total variation
- peak counts, rates, prominence, and intervals
- dominant frequency, spectral centroid, entropy, and band powers
- tremor power ratio and postural variability
- task-specific tapping, repetition, resting, gait, sway, transition, and turning features

The current pipeline summarizes 80 numeric extracted features. It does not train directly on raw samples.

Relevant implementation modules include:

- [src/build_dataset.py](./src/build_dataset.py)
- [src/preprocessing.py](./src/preprocessing.py)
- [src/common_features.py](./src/common_features.py)
- [src/frequency_features.py](./src/frequency_features.py)
- [src/task_features.py](./src/task_features.py)
- [src/feature_registry.py](./src/feature_registry.py)
- [src/label_mapping.py](./src/label_mapping.py)

## 4. Clinical score mapping

The active pipeline maps recordings to the supplied workbook items:

| Recording task | Workbook item |
|---|---:|
| Arm Extended Forward | 21 |
| Finger Tapping | 11 |
| Finger to Nose | 21 |
| Hand Resting | 6 |
| Fist Open and Close | 12 |
| Pronation Supination | 13 |
| Normal Walking | 16 |
| Quiet Standing | 17 |
| Sit-to-Stand | 15 |
| TUG | 15 |

This produces 50 labeled recordings across all participants. The mapping must be confirmed by a clinician before production use or interpretation.

## 5. Training and testing design

Recordings from the same participant are correlated. Randomly splitting recordings would leak participant-specific information into testing and inflate performance. The active trainer therefore uses participant-grouped evaluation:

1. Select held-out participants for the test set using a fixed random seed.
2. Train using all other participants.
3. Impute missing values using training data only.
4. Predict the held-out participant.
5. Report continuous MAE/RMSE and rounded-score accuracy.

No synthetic augmentation is used by the active Random Forest workflow.

## 6. Model and evaluation

The reusable training script uses a **Random Forest classifier** configured for classes 0, 1, 2, 3, and 4. Current labels contain scores 0–3; score 4 remains supported but is not represented in this dataset. The model uses median imputation, participant-grouped validation, and the dominant/non-dominant hand-side code where available.

The active ML workflow reports:

- Random Forest classification metrics for the five ordinal score classes
- participant-held-out validation with no cross-participant leakage
- continuous MAE/RMSE and rounded 0–4 ordinal accuracy

The reusable scikit-learn training code in [src/train_model.py](./src/train_model.py) is the active Random Forest training path. The older notebook output is retained as historical analysis and is not the active model artifact.

## 7. Current generated outputs

The latest pipeline run generated:

| Output | Current size |
|---|---:|
| Recording-level feature rows | 50 |
| Participant-task rows | 41 |
| Long-form feature rows | 2,409 |
| Registered features | 58 |
| Exploratory numeric features summarized | 80 |
| Valid recordings | 47 |
| Recordings needing quality review | 3 |
| Unresolved task labels | 0 |

Outputs are stored under `data/features/` and `reports/`. They are generated artifacts and should be regenerated after changing raw recordings or feature code.

## 8. Latest Random Forest training result

Training completed successfully on 10 November 2026 using the 50 labeled recording-level rows:

| Metric | Result |
|---|---:|
| Model | Random Forest classifier |
| Participants | 9 |
| Recordings | 50 |
| Training features | 78 |
| Validation | 5-fold GroupKFold by participant |
| MAE | 0.560 |
| RMSE | 1.020 |
| Ordinal accuracy | 68.0% |
| Macro-F1 | 0.279 |
| Pearson correlation | 0.599 |
| Predictions in 0–4 range | 100% |

The trained artifact is [reports/model/best_model.joblib](./reports/model/best_model.joblib), with metrics in [reports/model/metrics.json](./reports/model/metrics.json) and out-of-fold predictions in [reports/model/oof_predictions.csv](./reports/model/oof_predictions.csv). These are exploratory results, not clinical validation. Score 4 has no examples in the current labels, so performance for that class cannot be assessed.

## 9. Reproducing the notebook

From the `ml/` directory:

```bash
python -m jupyter nbconvert --to notebook --execute \
  clinical_score_training.ipynb \
  --output clinical_score_training.ipynb \
  --ExecutePreprocessor.timeout=120
```

Use [src/train_model.py](./src/train_model.py) for the active Random Forest workflow. The notebook is retained as historical exploratory work and is not the active model path.

## 10. What is needed next

1. Recollect or convert ratings to the official MDS-UPDRS Part III element structure.
2. Confirm every task-to-score mapping with the clinician.
3. The moved `Healthy Participants/HP004`–`HP006` recordings are included as three additional healthy participants, labeled with the study ground truth of 0; dominant/non-dominant side is retained as metadata and is not treated as a separate participant.
4. Add substantially more participants and repeated clinical assessments.
5. Compare models using nested, participant-grouped validation.
6. Repair and pin the Python scientific environment before relying on scikit-learn training.
7. Report confidence intervals and per-task/per-participant error distributions.

Until these steps are complete, the notebook is best viewed as a transparent data audit and feasibility experiment rather than a clinical model.
