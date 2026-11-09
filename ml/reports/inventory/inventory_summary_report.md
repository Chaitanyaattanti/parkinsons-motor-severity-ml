# Comprehensive Data Inventory & Signal Audit Report

## Executive Summary

- **Total Recording Files Discovered**: 50
- **Unique Confirmed Participants**: 9 ({'Healthy': 33, "Parkinson's Disease": 15, 'Atypical Parkinsonism': 2})
- **Distinct Clinical Motor Tasks**: 11
- **Recordings Passing Initial Validity**: 47 (94.0%)
- **Recordings with Quality Warnings**: 0
- **Unreadable / Invalid Files**: 3
- **Clinical label source**: Healthy recordings use cohort ground truth 0; PD task scores are sourced from `Clinical Score.xlsx` during dataset construction.

## Participant-by-Task Coverage Matrix

| participant_id   | diagnosis_group       | Arm Extended Forward   | Finger Tapping   | Finger to Nose   | Fist Open and Close   | Hand Resting   | Normal Walking   | Pronation Supination   | Quiet Standing   | Sit-to-Stand   | TUG          | Turning Task   |
|:-----------------|:----------------------|:-----------------------|:-----------------|:-----------------|:----------------------|:---------------|:-----------------|:-----------------------|:-----------------|:---------------|:-------------|:---------------|
| Atypical_PD001   | Atypical Parkinsonism | Missing                | Missing          | Missing          | Missing               | Missing        | Valid Signal     | Missing                | Valid Signal     | Missing        | Missing      | Missing        |
| HP001            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| HP002            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| HP003            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| HP004            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| HP005            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| HP006            | Healthy               | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| PD001            | Parkinson's Disease   | Valid Signal           | Valid Signal     | Valid Signal     | Missing               | Valid Signal   | Missing          | Missing                | Missing          | Missing        | Missing      | Missing        |
| PD002            | Parkinson's Disease   | Valid Signal           | Valid Signal     | Valid Signal     | Valid Signal          | Valid Signal   | Valid Signal     | Valid Signal           | Valid Signal     | Valid Signal   | Valid Signal | Valid Signal   |


## Task Recording Distribution

| task                 |   Atypical Parkinsonism |   Healthy |   Parkinson's Disease |
|:---------------------|------------------------:|----------:|----------------------:|
| Arm Extended Forward |                       0 |         6 |                     2 |
| Finger Tapping       |                       0 |         9 |                     2 |
| Finger to Nose       |                       0 |         9 |                     2 |
| Fist Open and Close  |                       0 |         0 |                     1 |
| Hand Resting         |                       0 |         9 |                     2 |
| Normal Walking       |                       1 |         0 |                     1 |
| Pronation Supination |                       0 |         0 |                     1 |
| Quiet Standing       |                       1 |         0 |                     1 |
| Sit-to-Stand         |                       0 |         0 |                     1 |
| TUG                  |                       0 |         0 |                     1 |
| Turning Task         |                       0 |         0 |                     1 |


## Key Findings & Critical Data Observations

1. **Complete Motor Battery Asymmetry**: Only `PD002` completed the full 11-task battery. `HP001`, `HP002`, `HP003`, and `PD001` completed exactly 4 upper-limb tasks (`Hand Resting`, `Arm Extended Forward`, `Finger Tapping`, `Finger to Nose`). `Atypical_PD001` completed only 2 tasks (`Normal Walking`, `Quiet Standing`).
2. **Nominal vs. Hardware Clock Discrepancy**: Device software outputs regular synthetic timestamps (e.g. 0.1s in HP/PD001, 0.05s in PD002) while internal `Metadata Time` reveals the actual hardware duration was ~61s rather than 88s, yielding a true acquisition rate of ~14.3 Hz rather than nominal 10 Hz / 20 Hz.
3. **Clinical label provenance**: `UPDRS Assessment Sheet.xlsx` is an empty rubric; task-level scores are supplied separately by `Clinical Score.xlsx` for PD001, PD002, and Atypical_PD001. Healthy recordings use the explicitly documented cohort-zero assumption.
