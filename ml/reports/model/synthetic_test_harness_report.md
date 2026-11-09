# Synthetic Mock Integration Test Verification Report

> [!NOTE]
> **Software Verification Only: Never Construe as Clinical Findings**
This report documents the verification of the machine-learning pipeline using synthetic mock participants. It confirms that preprocessing, imputation, scaling, and GroupKFold cross-validation operate without leakage.

- **Best Model**: random_forest
- **MAE**: 0.500
- **RMSE**: 0.707
- **Participant Leakage Check**: PASSED (100% disjoint groups across all folds)
