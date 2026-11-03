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

The public notebook [clinical_score_training.ipynb](./clinical_score_training.ipynb) contains the reproducible ML workflow with outputs cleared. Raw recordings, clinical workbooks, and derived feature tables are intentionally excluded; supply them locally before execution.

## 2. Data and labels

The local feature table is `data/features/recording_level_features.csv` (not included in this public repository). It contains 29 recordings from:

- 12 healthy recordings
- 15 Parkinson's disease recordings
- 2 atypical parkinsonism recordings

The clinician workbook is a local-only file and must not be committed to this public repository. It contains Part III scores for three unhealthy participants. The local analysis reported these aggregate totals:

| Group | Participants |
|---|---:|
| Unhealthy with clinician scores | 3 |

The workbook uses the project's earlier custom 33-item score structure. It is not automatically equivalent to the official MDS-UPDRS 3.1–3.18/33-element structure. The notebook therefore uses an explicit, exploratory task-to-score mapping and prints that limitation.

Healthy recordings have no clinician UPDRS scores. They are never assigned fabricated scores. The final model is trained on unhealthy recordings with clinician scores and applied to healthy recordings to produce exploratory 0–4 predictions; those predictions cannot be accuracy-tested without healthy clinician ratings.

## 3. Feature extraction

The pipeline extracts numeric features from each recording, including:

- signal level, range, RMS, variability, skewness, and kurtosis
- first/second differences, jerk proxies, and total variation
- peak counts, rates, prominence, and intervals
- dominant frequency, spectral centroid, entropy, and band powers
- tremor power ratio and postural variability
- task-specific tapping, repetition, resting, gait, sway, transition, and turning features

The current notebook uses 77 numeric extracted features. It does not train directly on raw samples.

Relevant implementation modules include:

- [src/build_dataset.py](./src/build_dataset.py)
- [src/preprocessing.py](./src/preprocessing.py)
- [src/common_features.py](./src/common_features.py)
- [src/frequency_features.py](./src/frequency_features.py)
- [src/task_features.py](./src/task_features.py)
- [src/feature_registry.py](./src/feature_registry.py)
- [src/label_mapping.py](./src/label_mapping.py)

## 4. Clinical score mapping

The notebook maps available task recordings to the supplied workbook items:

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

This produces 16 labeled recordings across three unhealthy participants. The mapping must be confirmed by a clinician before production use or interpretation.

## 5. Training and testing design

Recordings from the same participant are correlated. Randomly splitting recordings would leak participant-specific information into testing and inflate performance. The notebook therefore uses participant-held-out evaluation:

1. Select one participant as the test participant.
2. Train using all other participants.
3. Impute missing values and scale using training data only.
4. Predict the held-out participant.
5. Repeat for every labeled participant.

The participant-held-out score evaluation is an internal check on the unhealthy training data. The requested final inference trains on all 16 mapped unhealthy recordings and predicts scores for all 12 healthy recordings.

## 6. Model and evaluation

The notebook reports:

- a training-participant mean baseline
- ridge regression for continuous 0–4 score prediction
- final ridge regression trained on unhealthy recordings and applied to healthy recordings

## 7. Current executed results

### Task-level score prediction

| Method | MAE | RMSE |
|---|---:|---:|
| Mean baseline | 0.982 | 1.061 |
| Ridge | 1.194 | 1.434 |
| Augmented ridge | 1.572 | 1.728 |

The current participant-held-out Ridge result is exploratory and should not be treated as clinical performance.

### Healthy-recording 0–4 predictions

The notebook trains on the 16 mapped unhealthy recordings and applies the model to the 12 healthy recordings. It prints both continuous predictions clipped to 0–4 and rounded integer scores. These are exploratory predictions, not measured clinical outcomes, because healthy clinician ratings are not available.

## 8. Reproducing the notebook

From the project root:

```bash
python -m jupyter nbconvert --to notebook --execute \
  clinical_score_training.ipynb \
  --output clinical_score_training.ipynb \
  --ExecutePreprocessor.timeout=120
```

The notebook uses NumPy-based model code because the active environment currently has a binary compatibility problem between NumPy 2.5.3 and installed compiled packages such as pandas/scikit-learn. The production training scripts in [src/train_model.py](./src/train_model.py) should be used only after the environment is repaired and validated.

## 9. What is needed next

1. Recollect or convert ratings to the official MDS-UPDRS Part III element structure.
2. Confirm every task-to-score mapping with the clinician.
3. Obtain clinician ratings for healthy recordings if a supervised severity or diagnostic model requires them.
4. Add substantially more participants and repeated clinical assessments.
5. Compare models using nested, participant-grouped validation.
6. Repair and pin the Python scientific environment before relying on scikit-learn training.
7. Report confidence intervals and per-task/per-participant error distributions.

Until these steps are complete, the notebook is best viewed as a transparent data audit and feasibility experiment rather than a clinical model.
