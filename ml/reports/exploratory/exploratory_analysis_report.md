# Comprehensive Exploratory Data Analysis Report

## 1. Study Sample & Recording Cohort Overview

- **Total Recordings Analyzed**: 50
- **Unique Participants**: 9
- **Diagnosis Breakdown**: {'Healthy': 33, "Parkinson's Disease": 15, 'Atypical Parkinsonism': 2}
- **Verified Clinical Labels Available**: 0 (All 0-4 scores missing)

## 2. Descriptive Statistics Summary (First 15 Features)

| feature_name         |   valid_samples |   missing_samples |   missing_pct |     mean |      std |   median |      iqr |      min |      max |
|:---------------------|----------------:|------------------:|--------------:|---------:|---------:|---------:|---------:|---------:|---------:|
| hand_side_code       |              21 |                29 |            58 |  0.57143 |  0.50709 |  1       |  1       |  0       |  1       |
| recording_duration_s |              50 |                 0 |             0 | 56.2565  | 37.5407  | 74.1032  | 78.8474  |  0       | 91       |
| sampling_rate_hz     |              40 |                10 |            20 | 12.1508  |  3.13914 | 10       |  6.6046  | 10       | 16.6381  |
| signal_mean          |              40 |                10 |            20 |  0.01098 |  0.03738 |  0.00109 |  0.00309 | -0.00225 |  0.20111 |
| signal_median        |              40 |                10 |            20 |  0.01027 |  0.03555 |  0.00153 |  0.00307 | -0.00305 |  0.18668 |
| signal_std           |              40 |                10 |            20 |  0.00721 |  0.02111 |  0.0025  |  0.00057 |  0.00176 |  0.13315 |
| signal_var           |              40 |                10 |            20 |  0.00049 |  0.0028  |  1e-05   |  0       |  0       |  0.01773 |
| signal_min           |              40 |                10 |            20 | -0.00667 |  0.00368 | -0.00612 |  0.00456 | -0.01679 |  0       |
| signal_max           |              40 |                10 |            20 |  0.02971 |  0.07476 |  0.01075 |  0.00502 |  0.00613 |  0.45467 |
| signal_range         |              40 |                10 |            20 |  0.03638 |  0.07501 |  0.0176  |  0.00452 |  0.01073 |  0.46289 |
| signal_rms           |              40 |                10 |            20 |  0.01429 |  0.04253 |  0.00321 |  0.00156 |  0.00184 |  0.24108 |
| signal_abs_mean      |              40 |                10 |            20 |  0.01234 |  0.03702 |  0.00251 |  0.00166 |  0.00128 |  0.20133 |
| signal_mad_mean      |              40 |                10 |            20 |  0.00596 |  0.01839 |  0.00195 |  0.00055 |  0.00132 |  0.11602 |
| signal_mad_median    |              40 |                10 |            20 |  0.00556 |  0.01793 |  0.00153 |  1e-05   |  0.00152 |  0.1131  |
| signal_p10           |              40 |                10 |            20 |  0.00211 |  0.01784 | -0.00153 |  0.00459 | -0.0061  |  0.10688 |


## 3. Methodological Discussion & Biomarker Caveats

> [!CAUTION]
> **Critical Research Boundary: Do Not Claim Biomarkers on Small Samples**
Although exploratory differences in signal standard deviation and peak rates can be observed between PD patients and healthy participants, **these cannot be claimed as validated Parkinson's biomarkers**. The present dataset has only 3 PD patients and 3 healthy controls. Such differences may reflect sensor fit, task execution speed, contact pressure, or individual participant habituation rather than motor severity.

## 4. Key Biomedical Signal Findings

1. **Observable Bandwidth**: At nominal $f_s = 10\text{ Hz}$, the Nyquist limit is strictly $5\text{ Hz}$. Resting tremor ($3-5\text{ Hz}$) is within the observable range, but higher frequency postural and action tremors ($5-12\text{ Hz}$) cannot be resolved without aliasing.
2. **Task Completion Asymmetry**: Normal walking and quiet standing were only recorded for 2 patients (`PD002`, `Atypical_PD001`) and 0 healthy controls in the available dataset. Upper-limb tasks have the widest coverage across 5 participants.
