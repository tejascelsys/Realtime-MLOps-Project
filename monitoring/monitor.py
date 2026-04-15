#!/usr/bin/env python3
"""
Evidently AI — Model Monitoring Report Generator.
Generates data drift, model performance, and prediction drift reports.

Usage:
    python monitoring/monitor.py                    # baseline comparison
    python monitoring/simulate_drift.py && python monitoring/monitor.py   # with drift
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path

from evidently.report import Report
from evidently.metric_preset import (
    DataDriftPreset,
    DataQualityPreset,
    ClassificationPreset,
)

from evidently.metrics import (
    ColumnDriftMetric,
    DatasetDriftMetric,
    DatasetMissingValuesMetric,
    ColumnDistributionMetric,
)
# ─── Paths ───────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "churn_data.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "churn_model.pkl"
METRICS_PATH = PROJECT_ROOT / "metrics.json"
DRIFTED_DATA_PATH = Path(__file__).resolve().parent / "drifted_data.csv"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

FEATURES = ["age", "tenure_months", "monthly_charges", "total_charges", "num_support_calls"]
TARGET = "churn"


def load_model():
    """Load the trained model."""
    if not MODEL_PATH.exists():
        print("⚠️  Model not found. Run 'dvc repro' first.")
        sys.exit(1)
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def load_data():
    """Load reference and current datasets."""
    if not DATA_PATH.exists():
        print("⚠️  Training data not found. Run 'dvc repro' first.")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)

    # Add predictions from the model
    model = load_model()
    df["prediction"] = model.predict(df[FEATURES])
    df["prediction_proba"] = model.predict_proba(df[FEATURES])[:, 1]

    # Split: 70% reference, 30% current (simulates training vs production)
    split_idx = int(len(df) * 0.7)
    reference = df.iloc[:split_idx].copy().reset_index(drop=True)

    # If drifted data exists, use it; otherwise use the remaining 30%
    if DRIFTED_DATA_PATH.exists():
        print("📊 Using drifted data for comparison (drift simulation active)")
        current = pd.read_csv(DRIFTED_DATA_PATH)
        current["prediction"] = model.predict(current[FEATURES])
        current["prediction_proba"] = model.predict_proba(current[FEATURES])[:, 1]
        # Recalculate churn based on drifted features for ground truth
        churn_prob = (
            (current["monthly_charges"] / 120) * 0.3
            + (current["num_support_calls"] / 10) * 0.4
            + (1 - current["tenure_months"] / 72) * 0.3
        )
        current["churn"] = (np.random.RandomState(42).random(len(current)) < churn_prob).astype(int)
    else:
        print("📊 Using training data split for comparison (no drift)")
        current = df.iloc[split_idx:].copy().reset_index(drop=True)

    return reference, current


def generate_data_drift_report(reference, current):
    """Generate a data drift report comparing distributions."""
    report = Report(metrics=[
        DatasetDriftMetric(),
        DatasetMissingValuesMetric(),
        ColumnDriftMetric(column_name="age"),
        ColumnDriftMetric(column_name="tenure_months"),
        ColumnDriftMetric(column_name="monthly_charges"),
        ColumnDriftMetric(column_name="total_charges"),
        ColumnDriftMetric(column_name="num_support_calls"),
        ColumnDriftMetric(column_name="prediction"),
    ])
    report.run(reference_data=reference, current_data=current)
    output_path = REPORTS_DIR / "data_drift_report.html"
    report.save_html(str(output_path))
    print(f"  ✅ Data Drift Report → {output_path.name}")
    return report


def generate_model_performance_report(reference, current):
    """Generate a model performance report with classification metrics."""
    report = Report(metrics=[
        ClassificationPreset(),
    ])
    # Evidently needs 'target' and 'prediction' columns
    ref_data = reference.rename(columns={"churn": "target"})
    cur_data = current.rename(columns={"churn": "target"})

    report.run(reference_data=ref_data, current_data=cur_data)
    output_path = REPORTS_DIR / "model_performance_report.html"
    report.save_html(str(output_path))
    print(f"  ✅ Model Performance Report → {output_path.name}")
    return report


def generate_data_quality_report(reference, current):
    """Generate a data quality report."""
    report = Report(metrics=[
        DataQualityPreset(),
    ])
    report.run(reference_data=reference, current_data=current)
    output_path = REPORTS_DIR / "data_quality_report.html"
    report.save_html(str(output_path))
    print(f"  ✅ Data Quality Report → {output_path.name}")
    return report


def load_model_metrics():
    """Load metrics from metrics.json."""
    if METRICS_PATH.exists():
        with open(METRICS_PATH, "r") as f:
            return json.load(f)
    return {"accuracy": "N/A", "auc_roc": "N/A"}


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n╔══════════════════════════════════════════════════╗")
    print("║   📊 Evidently AI — Monitoring Report Generator  ║")
    print("╚══════════════════════════════════════════════════╝\n")

    # Load data
    reference, current = load_data()
    print(f"  Reference samples: {len(reference)}")
    print(f"  Current samples:   {len(current)}")
    print()

    # Load model metrics
    metrics = load_model_metrics()
    print(f"  Model Accuracy: {metrics.get('accuracy', 'N/A')}")
    print(f"  Model AUC-ROC:  {metrics.get('auc_roc', 'N/A')}")
    print()

    # Generate reports
    print("  Generating reports...\n")
    generate_data_drift_report(reference, current)
    generate_model_performance_report(reference, current)
    generate_data_quality_report(reference, current)

    print(f"\n  📂 All reports saved to: monitoring/reports/")
    print(f"  🌐 View at: http://localhost:5000/monitoring\n")

    # Save summary as JSON for the UI
    summary = {
        "reference_samples": len(reference),
        "current_samples": len(current),
        "model_accuracy": metrics.get("accuracy", "N/A"),
        "model_auc_roc": metrics.get("auc_roc", "N/A"),
        "drift_source": "drifted" if DRIFTED_DATA_PATH.exists() else "training_split",
        "reports": [
            "data_drift_report.html",
            "model_performance_report.html",
            "data_quality_report.html",
        ],
    }
    with open(REPORTS_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
