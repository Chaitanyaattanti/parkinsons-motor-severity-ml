"""Configuration settings for Parkinson's motor severity pipeline.

All paths, thresholds, and parameters are defined centrally and can be
overridden via environment variables or command-line arguments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    """Master configuration dataclass for the Parkinson's motor severity pipeline."""

    # Project directories
    project_root: Path = field(default_factory=lambda: Path(os.environ.get("PROJECT_ROOT", ".")).resolve())
    healthy_dir_name: str = "Healthy Participants"
    pd_dir_name: str = "PD Patients"
    
    # Clinical documents
    clinical_updrs_sheet: str = "UPDRS Assessment Sheet.xlsx"
    clinical_score_workbook: str = "Clinical Score.xlsx"
    clinical_protocol_sheet: str = "Patient Tests and Parameters for Data Collection.xlsx"

    # Data output directories
    processed_dir: Path = field(default_factory=lambda: Path("data/processed"))
    features_dir: Path = field(default_factory=lambda: Path("data/features"))
    
    # Reports directories
    reports_inventory_dir: Path = field(default_factory=lambda: Path("reports/inventory"))
    reports_quality_dir: Path = field(default_factory=lambda: Path("reports/quality"))
    reports_exploratory_dir: Path = field(default_factory=lambda: Path("reports/exploratory"))
    reports_labels_dir: Path = field(default_factory=lambda: Path("reports/labels"))
    reports_features_dir: Path = field(default_factory=lambda: Path("reports/features"))
    reports_model_dir: Path = field(default_factory=lambda: Path("reports/model"))

    # Quality Control thresholds
    min_samples_per_trial: int = 10
    min_duration_s: float = 3.0
    max_gap_factor: float = 3.0  # Gap flagged if dt > max_gap_factor * median(dt)
    constant_signal_variance_threshold: float = 1e-9
    clipping_quantile_threshold: float = 0.999
    
    # Signal and Sampling assumptions
    nominal_fs_hz: float = 10.0  # Nominal sampling frequency
    min_observable_frequency_hz: float = 0.5
    tremor_low_band: tuple[float, float] = (0.5, 3.0)
    tremor_parkinsonian_band: tuple[float, float] = (3.0, 5.0)  # Observable band at 10 Hz fs
    tremor_high_band: tuple[float, float] = (5.0, 10.0)  # Requires fs >= 20 Hz (Nyquist >= 10 Hz)
    
    # Feature Engineering
    ddof: int = 1  # Sample standard deviation degrees of freedom
    cv_min_mean_threshold: float = 1e-5  # Safe minimum absolute mean for CV
    peak_prominence_std_factor: float = 0.4
    peak_min_distance_s: float = 0.15

    # Reproducibility
    random_state: int = 42

    def ensure_directories(self) -> None:
        """Create all required output folders if they do not already exist."""
        for path in [
            self.processed_dir,
            self.features_dir,
            self.reports_inventory_dir,
            self.reports_quality_dir,
            self.reports_exploratory_dir,
            self.reports_labels_dir,
            self.reports_features_dir,
            self.reports_model_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


DEFAULT_CONFIG = PipelineConfig()
