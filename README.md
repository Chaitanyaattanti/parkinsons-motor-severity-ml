# Parkinson's Motor Severity Project

This repository is split into two independent areas:

- [app/](./app/) — clinician-facing MDS-UPDRS assessment web application. See [app/README.md](./app/README.md).
- [ml/](./ml/) — sensor-data processing, feature extraction, labels, Random Forest training, tests, and reports. See [ml/README.md](./ml/README.md).

## Run the application

```bash
python app/run_app.py
```

## Run the ML workflow

```bash
cd ml
python -m src.pipeline
```

The ML work is exploratory and is not clinically validated.

Current ML outputs contain 50 recordings from 9 participants, with 50 task-level labels, 47 recordings passing signal validity checks, and 3 requiring quality review. Random Forest training completed with grouped-validation MAE 0.560 and ordinal accuracy 68.0%. See [ml/README.md](./ml/README.md) for complete statistics and limitations.
