# Model Training & Grouped Evaluation Comparison Report

- **Target Score**: clinical_score
- **Status**: SUCCESS
- **Number of Participants**: 9
- **Number of Recordings**: 50
- **Validation Scheme**: GroupKFold / Leave-One-Participant-Out

## Cross-Validation Performance Summary

| Model         |   MAE |   RMSE |   Pearson r |   % In Valid Range [0, 4] |
|:--------------|------:|-------:|------------:|--------------------------:|
| random_forest |  0.56 |   1.02 |       0.599 |                       100 |


## Methodological Warnings & Limitations

- Small sample size (N=9 participants). Results have high uncertainty.
- Grouped cross-validation was strictly maintained by participant_id.
- Random Forest predictions are evaluated as continuous estimates and rounded to ordinal scores 0-4.

