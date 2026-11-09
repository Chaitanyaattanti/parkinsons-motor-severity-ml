"""Master end-to-end reproducible pipeline execution script.

Orchestrates data inventory, signal quality checks, feature extraction, dataset construction,
clinical label auditing, exploratory analysis, and model readiness assessment.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.build_dataset import build_master_datasets
from src.config import DEFAULT_CONFIG, PipelineConfig
from src.data_inventory import run_inventory
from src.exploratory_analysis import run_exploratory_analysis
from src.feature_registry import export_feature_registry
from src.label_mapping import generate_label_mapping_artifacts
from src.train_model import check_model_readiness, run_synthetic_integration_test


def run_pipeline(config: PipelineConfig | None = None) -> int:
    """Execute all phases of the Parkinson's motor severity pipeline."""
    cfg = config or DEFAULT_CONFIG
    cfg.ensure_directories()

    start_time = time.time()
    print("=" * 70)
    print("  PARKINSON'S MOTOR SEVERITY ESTIMATION RESEARCH PIPELINE")
    print("=" * 70)
    print(f"Project root: {cfg.project_root.resolve()}")

    # Phase 1: Data Inventory
    print("\n--- Phase 1: Automated Data Inventory & Coverage Audit ---")
    df_inv, df_matrix = run_inventory(cfg)
    print(f"Discovered {len(df_inv)} files across {df_inv['participant_id'].nunique()} participants.")
    print(f"Inventory saved to: {cfg.reports_inventory_dir / 'data_inventory.csv'}")
    print(f"Coverage matrix saved to: {cfg.reports_inventory_dir / 'participant_task_matrix.csv'}")

    # Phase 2: Feature Registry
    print("\n--- Phase 2: Feature Registry Export ---")
    df_reg = export_feature_registry(cfg)
    print(f"Exported {len(df_reg)} registered feature definitions to {cfg.reports_features_dir / 'feature_registry.csv'}")

    # Phase 3: Dataset Construction (Validation, Preprocessing, Feature Extraction)
    print("\n--- Phase 3: Signal Preprocessing & Master Dataset Construction ---")
    df_rec, df_part_task, df_long = build_master_datasets(cfg)
    print(f"Recording-level dataset: {len(df_rec)} rows, {df_rec.shape[1]} columns -> {cfg.features_dir / 'recording_level_features.csv'}")
    print(f"Participant-task dataset: {len(df_part_task)} rows, {df_part_task.shape[1]} columns -> {cfg.features_dir / 'participant_task_features.csv'}")
    print(f"Long-form dataset: {len(df_long)} rows -> {cfg.features_dir / 'long_form_features.csv'}")

    # Phase 4: Clinical Label Audit & Mapping Template
    print("\n--- Phase 4: Clinical Label Audit & MDS-UPDRS Mapping ---")
    df_tmpl, df_unres = generate_label_mapping_artifacts(df_rec, cfg)
    print(f"Generated clinician template: {len(df_tmpl)} rows -> {cfg.reports_labels_dir / 'label_mapping_template.csv'}")
    print(f"Unresolved labels: {len(df_unres)} -> {cfg.reports_labels_dir / 'unresolved_clinical_labels.csv'}")

    # Phase 5: Exploratory Analysis & Figures
    print("\n--- Phase 5: Exploratory Data Analysis & Scientific Visualization ---")
    exp_res = run_exploratory_analysis(df_rec, cfg)
    print(f"Analyzed {exp_res['n_features_analyzed']} features.")
    print(f"Descriptive statistics: {cfg.reports_exploratory_dir / 'descriptive_statistics.csv'}")
    print(f"Exploratory plots saved to: {cfg.reports_exploratory_dir}")

    # Phase 6: Model Readiness & Evaluation Harness
    print("\n--- Phase 6: Model Readiness Audit & ML Evaluation Harness ---")
    readiness = check_model_readiness(df_rec, "clinical_score")
    print(f"Supervised ML Readiness Status: {readiness['status']}")
    print(f"Reason: {readiness['reason']}")

    audit_md_path = cfg.reports_model_dir / "model_readiness_audit.md"
    audit_text = [
        "# Supervised Model Readiness Audit Report\n",
        f"- **Dataset Evaluated**: `{cfg.features_dir / 'recording_level_features.csv'}`",
        "- **Target Column Evaluated**: `clinical_score`",
        f"- **Supervised Model Training Readiness**: **{'READY' if readiness['ready'] else 'BLOCKED'}**",
        f"- **Status Code**: `{readiness['status']}`",
        f"- **Labeled Participants Found**: {readiness['n_labeled_participants']}",
        f"- **Labeled Recordings Found**: {readiness['n_labeled_rows']}",
        f"- **Detailed Reason**: {readiness['reason']}\n",
        "## Recommended Next Steps",
        "1. Confirm the provisional task-to-score mapping with a clinician.",
        "2. Ensure assessment dates and medication states match each recording session.",
        "3. Add more participants and evaluate the model on an independent cohort.\n",
    ]
    audit_md_path.write_text("\n".join(audit_text), encoding="utf-8")

    # Run synthetic harness test to verify ML code executes cleanly without leakage
    print("Verifying grouped cross-validation ML harness on synthetic benchmark...")
    synth_res = run_synthetic_integration_test(cfg)
    print(f"Synthetic test verification passed: Best model '{synth_res['selected_model']}' (MAE: {synth_res['models'][synth_res['selected_model']]['mae']:.3f})")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  PIPELINE EXECUTION COMPLETE in {elapsed:.2f} seconds")
    print("=" * 70)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Parkinson's motor severity pipeline")
    parser.add_argument("--root", default=".", help="Project workspace root directory")
    args = parser.parse_args()

    cfg = PipelineConfig(project_root=Path(args.root).resolve())
    sys.exit(run_pipeline(cfg))


if __name__ == "__main__":
    main()
