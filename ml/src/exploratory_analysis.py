"""Exploratory data analysis, statistical summaries, and publication-quality plots.

Generates descriptive statistics, coverage matrices, signal comparisons,
feature distributions, and spectral analysis reports.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Ensure matplotlib runs in headless mode and uses a writable cache
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd

from src.config import DEFAULT_CONFIG, PipelineConfig
from src.preprocessing import SignalPreprocessor


def run_exploratory_analysis(
    df_rec: pd.DataFrame,
    config: PipelineConfig | None = None,
) -> dict[str, Any]:
    """Execute exploratory analysis pipeline and output all plots and statistical tables."""
    cfg = config or DEFAULT_CONFIG
    cfg.ensure_directories()
    out_dir = cfg.reports_exploratory_dir

    # 1. Descriptive Statistics Table
    numeric_cols = df_rec.select_dtypes(include=[np.number]).columns.tolist()
    # Filter out identifier-like numeric columns
    feature_cols = [c for c in numeric_cols if c not in ["clinical_score"]]

    desc_rows = []
    for col in feature_cols:
        s = df_rec[col]
        valid_cnt = int(s.notnull().sum())
        total_cnt = len(s)
        pct_missing = float((total_cnt - valid_cnt) / total_cnt * 100.0) if total_cnt > 0 else 0.0

        desc_rows.append({
            "feature_name": col,
            "valid_samples": valid_cnt,
            "missing_samples": total_cnt - valid_cnt,
            "missing_pct": round(pct_missing, 1),
            "mean": round(float(s.mean()), 5) if valid_cnt > 0 else np.nan,
            "std": round(float(s.std()), 5) if valid_cnt > 1 else np.nan,
            "median": round(float(s.median()), 5) if valid_cnt > 0 else np.nan,
            "iqr": round(float(s.quantile(0.75) - s.quantile(0.25)), 5) if valid_cnt > 0 else np.nan,
            "min": round(float(s.min()), 5) if valid_cnt > 0 else np.nan,
            "max": round(float(s.max()), 5) if valid_cnt > 0 else np.nan,
        })

    df_desc = pd.DataFrame(desc_rows)
    desc_csv_path = out_dir / "descriptive_statistics.csv"
    df_desc.to_csv(desc_csv_path, index=False)

    # 2. Plot: Task Coverage Heatmap
    plot_task_coverage(df_rec, out_dir / "task_coverage_heatmap.png")

    # 3. Plot: Representative Sensor Traces
    plot_representative_signals(df_rec, cfg, out_dir / "representative_signals_comparison.png")

    # 4. Plot: Feature Distributions
    plot_feature_distributions(df_rec, out_dir / "feature_distributions_boxplots.png")

    # 5. Plot: Feature Correlation Matrix
    plot_correlation_matrix(df_rec, out_dir / "feature_correlation_matrix.png")

    # 6. Plot: Spectral Density & Nyquist Limit
    plot_spectral_nyquist(df_rec, cfg, out_dir / "spectral_density_nyquist.png")

    # 7. Generate Comprehensive Markdown Report
    report_md_path = out_dir / "exploratory_analysis_report.md"
    generate_exploratory_markdown(df_rec, df_desc, report_md_path)

    return {
        "n_features_analyzed": len(feature_cols),
        "descriptive_csv": str(desc_csv_path),
        "report_md": str(report_md_path),
    }


def plot_task_coverage(df_rec: pd.DataFrame, out_path: Path) -> None:
    """Generate participant-by-task availability heatmap."""
    participants = sorted(df_rec["participant_id"].unique())
    tasks = sorted(df_rec["task"].unique())

    matrix = np.zeros((len(participants), len(tasks)))
    for i, p in enumerate(participants):
        p_tasks = set(df_rec[df_rec["participant_id"] == p]["task"])
        for j, t in enumerate(tasks):
            if t in p_tasks:
                matrix[i, j] = 1.0  # Available

    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    cax = ax.imshow(matrix, cmap="Blues", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels(tasks, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(participants)))
    ax.set_yticklabels(participants, fontsize=10)

    # Annotate cells
    for i in range(len(participants)):
        for j in range(len(tasks)):
            status = "Present" if matrix[i, j] == 1.0 else "Missing"
            color = "white" if matrix[i, j] == 1.0 else "#777777"
            ax.text(j, i, status, ha="center", va="center", color=color, fontsize=8, fontweight="bold")

    ax.set_title("Participant Task Coverage Matrix (Present vs Missing)", fontsize=12, pad=12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_representative_signals(df_rec: pd.DataFrame, config: PipelineConfig, out_path: Path) -> None:
    """Plot representative time-series traces comparing PD vs Healthy participants."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=150)
    preprocessor = SignalPreprocessor(config)

    tasks_to_plot = [
        ("Hand Resting", axes[0, 0]),
        ("Finger Tapping", axes[0, 1]),
        ("Arm Extended Forward", axes[1, 0]),
        ("Finger to Nose", axes[1, 1]),
    ]

    for task_name, ax in tasks_to_plot:
        # Pick one healthy and one PD recording
        hp_row = df_rec[(df_rec["task"] == task_name) & (df_rec["diagnosis"] == "Healthy")]
        pd_row = df_rec[(df_rec["task"] == task_name) & (df_rec["diagnosis"] == "Parkinson's Disease")]

        if len(hp_row) > 0:
            hp_path = config.project_root / hp_row.iloc[0]["file_path"]
            hp_df = pd.read_excel(hp_path, sheet_name="mySet" if "mySet" in openpyxl.load_workbook(hp_path, read_only=True).sheetnames else 0)
            hp_proc = preprocessor.process(hp_df, str(hp_path), hp_row.iloc[0]["participant_id"], task_name)
            t_plot = hp_proc.time[:300]
            y_plot = hp_proc.signal[:300]
            ax.plot(t_plot - t_plot[0], y_plot, label=f"Healthy ({hp_row.iloc[0]['participant_id']})", color="#2b5c8f", lw=1.2)

        if len(pd_row) > 0:
            pd_path = config.project_root / pd_row.iloc[0]["file_path"]
            if pd_path.suffix.lower() == ".xlsx":
                pd_df = pd.read_excel(pd_path, sheet_name="mySet" if "mySet" in openpyxl.load_workbook(pd_path, read_only=True).sheetnames else 0)
            else:
                pd_df = pd.read_csv(pd_path)
            pd_proc = preprocessor.process(pd_df, str(pd_path), pd_row.iloc[0]["participant_id"], task_name)
            t_plot = pd_proc.time[:300]
            y_plot = pd_proc.signal[:300]
            ax.plot(t_plot - t_plot[0], y_plot, label=f"PD ({pd_row.iloc[0]['participant_id']})", color="#c23b22", lw=1.2, alpha=0.85)

        ax.set_title(f"Task: {task_name}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Elapsed Time (s)", fontsize=9)
        ax.set_ylabel("Normalized Resistance (ΔR/R0)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(fontsize=8, loc="upper right")

    fig.suptitle("Representative Resistance Sensor Signals (First ~20-30s Segment)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_feature_distributions(df_rec: pd.DataFrame, out_path: Path) -> None:
    """Plot feature distribution comparisons between diagnosis groups."""
    features_to_plot = [
        ("signal_std", "Signal Amplitude Std (Variability)"),
        ("diff_abs_mean", "Mean Absolute First Difference (Roughness)"),
        ("peak_rate_per_sec", "Detected Peak Rate (Hz)"),
        ("spectral_entropy", "Spectral Entropy"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=150)
    axes = axes.flatten()

    for idx, (feat_col, feat_title) in enumerate(features_to_plot):
        ax = axes[idx]
        groups = []
        labels = []
        for g_name in ["Healthy", "Parkinson's Disease"]:
            vals = df_rec[df_rec["diagnosis"] == g_name][feat_col].dropna().values
            if len(vals) > 0:
                groups.append(vals)
                labels.append(f"{g_name}\n(N={len(vals)})")

        if groups:
            box = ax.boxplot(groups, labels=labels, patch_artist=True, showmeans=True)
            colors = ["#7293cb", "#e1974c"]
            for patch, col in zip(box["boxes"], colors):
                patch.set_facecolor(col)
                patch.set_alpha(0.7)

            # Jittered scatter overlay
            for i, vals in enumerate(groups, 1):
                jitter = np.random.normal(0, 0.04, size=len(vals))
                ax.scatter(np.full_like(vals, i) + jitter, vals, color="black", alpha=0.6, s=20, zorder=3)

        ax.set_title(feat_title, fontsize=10, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5)

    fig.suptitle("Exploratory Feature Distributions by Diagnosis Group", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_correlation_matrix(df_rec: pd.DataFrame, out_path: Path) -> None:
    """Plot correlation heatmap among selected primary features."""
    selected_features = [
        "signal_mean", "signal_std", "signal_rms", "signal_range",
        "diff_abs_mean", "total_variation", "peak_rate_per_sec",
        "dominant_frequency_hz", "spectral_entropy", "band_power_parkinsonian_3_0_to_5_0_hz"
    ]
    present_cols = [c for c in selected_features if c in df_rec.columns]
    corr = df_rec[present_cols].corr()

    fig, ax = plt.subplots(figsize=(9, 8), dpi=150)
    cax = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(range(len(present_cols)))
    ax.set_xticklabels(present_cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(present_cols)))
    ax.set_yticklabels(present_cols, fontsize=8)

    for i in range(len(present_cols)):
        for j in range(len(present_cols)):
            val = corr.iloc[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", color="black" if abs(val) < 0.6 else "white", fontsize=7)

    ax.set_title("Correlation Matrix of Key Biomechanical Features", fontsize=11, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_spectral_nyquist(df_rec: pd.DataFrame, config: PipelineConfig, out_path: Path) -> None:
    """Illustrate the 5 Hz Nyquist frequency constraint for 10 Hz vs 16.6 Hz recordings."""
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    preprocessor = SignalPreprocessor(config)

    # Plot Welch PSD for HP001 (10 Hz) vs PD002 (16.6 Hz) on Hand Resting
    hp_row = df_rec[(df_rec["task"] == "Hand Resting") & (df_rec["participant_id"] == "HP001")]
    pd_row = df_rec[(df_rec["task"] == "Hand Resting") & (df_rec["participant_id"] == "PD002")]

    from scipy.signal import welch

    if len(hp_row) > 0:
        p = config.project_root / hp_row.iloc[0]["file_path"]
        df_raw = pd.read_excel(p, sheet_name=0)
        proc = preprocessor.process(df_raw, str(p), "HP001", "Hand Resting")
        freqs, psd = welch(proc.signal_detrended, fs=proc.fs_effective, nperseg=min(256, len(proc.signal)))
        ax.plot(freqs, psd, label=f"HP001 (fs = {proc.fs_effective:.1f} Hz, Nyquist = {proc.fs_effective/2:.1f} Hz)", color="#2b5c8f", lw=1.5)

    if len(pd_row) > 0:
        p = config.project_root / pd_row.iloc[0]["file_path"]
        df_raw = pd.read_excel(p, sheet_name=0)
        proc = preprocessor.process(df_raw, str(p), "PD002", "Hand Resting")
        freqs, psd = welch(proc.signal_detrended, fs=proc.fs_effective, nperseg=min(256, len(proc.signal)))
        ax.plot(freqs, psd, label=f"PD002 (fs = {proc.fs_effective:.1f} Hz, Nyquist = {proc.fs_effective/2:.1f} Hz)", color="#c23b22", lw=1.5)

    # Vertical bands
    ax.axvspan(3.0, 5.0, color="orange", alpha=0.15, label="Parkinsonian Rest Tremor Band (3-5 Hz)")
    ax.axvline(5.0, color="red", linestyle="--", lw=1.5, label="10 Hz Nyquist Cutoff (5.0 Hz)")
    ax.axvspan(5.0, 10.0, color="gray", alpha=0.1, label="Unobservable Postural Tremor (> 5 Hz at fs=10Hz)")

    ax.set_title("Power Spectral Density & The 5 Hz Nyquist Boundary Limitation", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (Hz)", fontsize=10)
    ax.set_ylabel("Power Spectral Density ((ΔR/R0)^2 / Hz)", fontsize=10)
    ax.set_xlim(0, 8.5)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8, loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def generate_exploratory_markdown(df_rec: pd.DataFrame, df_desc: pd.DataFrame, out_path: Path) -> None:
    """Generate comprehensive markdown exploratory report."""
    md = []
    md.append("# Comprehensive Exploratory Data Analysis Report\n")
    md.append("## 1. Study Sample & Recording Cohort Overview\n")
    md.append(f"- **Total Recordings Analyzed**: {len(df_rec)}")
    md.append(f"- **Unique Participants**: {df_rec['participant_id'].nunique()}")
    md.append(f"- **Diagnosis Breakdown**: {df_rec['diagnosis'].value_counts().to_dict()}")
    md.append(f"- **Verified Clinical Labels Available**: 0 (All 0-4 scores missing)\n")

    md.append("## 2. Descriptive Statistics Summary (First 15 Features)\n")
    md.append(df_desc.head(15).to_markdown(index=False))
    md.append("\n")

    md.append("## 3. Methodological Discussion & Biomarker Caveats\n")
    md.append("> [!CAUTION]\n> **Critical Research Boundary: Do Not Claim Biomarkers on Small Samples**")
    md.append("Although exploratory differences in signal standard deviation and peak rates can be observed between PD patients and healthy participants, **these cannot be claimed as validated Parkinson's biomarkers**. The present dataset has only 3 PD patients and 3 healthy controls. Such differences may reflect sensor fit, task execution speed, contact pressure, or individual participant habituation rather than motor severity.\n")

    md.append("## 4. Key Biomedical Signal Findings\n")
    md.append("1. **Observable Bandwidth**: At nominal $f_s = 10\\text{ Hz}$, the Nyquist limit is strictly $5\\text{ Hz}$. Resting tremor ($3-5\\text{ Hz}$) is within the observable range, but higher frequency postural and action tremors ($5-12\\text{ Hz}$) cannot be resolved without aliasing.")
    md.append("2. **Task Completion Asymmetry**: Normal walking and quiet standing were only recorded for 2 patients (`PD002`, `Atypical_PD001`) and 0 healthy controls in the available dataset. Upper-limb tasks have the widest coverage across 5 participants.\n")

    out_path.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    from src.build_dataset import build_master_datasets
    df_r, _, _ = build_master_datasets()
    res = run_exploratory_analysis(df_r)
    print(f"Exploratory analysis complete: {res['n_features_analyzed']} features analyzed.")
