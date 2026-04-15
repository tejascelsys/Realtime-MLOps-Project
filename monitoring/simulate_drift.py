#!/usr/bin/env python3
"""
Drift Simulator — Generates synthetic production data with distribution shifts.
Run this before monitor.py to see drift detection in action.

Usage:
    python monitoring/simulate_drift.py          # generate drifted data
    python monitoring/monitor.py                  # see drift in reports
    rm monitoring/drifted_data.csv                # reset to baseline
"""

import yaml
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = PROJECT_ROOT / "params.yaml"
OUTPUT_PATH = Path(__file__).resolve().parent / "drifted_data.csv"

with open(PARAMS_PATH, "r") as f:
    params = yaml.safe_load(f)


def generate_drifted_data():
    """
    Generate data with realistic distribution shifts to simulate production drift.

    Drift scenarios applied:
    1. monthly_charges shifted UP by ~40% (price increase scenario)
    2. num_support_calls shifted UP by ~3x (service quality degradation)
    3. tenure_months shifted DOWN (influx of new, short-tenure customers)
    4. age distribution stays similar (demographic doesn't change much)
    """
    np.random.seed(99)  # Different seed than training for different distribution
    n_samples = params["data"]["n_samples"]

    data = {
        "customer_id": range(1, n_samples + 1),
        # Age: similar distribution (minimal drift)
        "age": np.random.randint(20, 65, n_samples),
        # Tenure: shifted DOWN — lots of new customers (was 1-72, now 1-30)
        "tenure_months": np.random.randint(1, 30, n_samples),
        # Monthly charges: shifted UP by ~40% (was 20-120, now 50-180)
        "monthly_charges": np.random.uniform(50, 180, n_samples),
        # Total charges: adjusted for lower tenure
        "total_charges": np.random.uniform(50, 4000, n_samples),
        # Support calls: shifted UP significantly (was 0-10, now 2-15)
        "num_support_calls": np.random.randint(2, 15, n_samples),
    }

    # Churn logic (same formula as generate_data.py)
    churn_prob = (
        (data["monthly_charges"] / 120) * 0.3
        + (data["num_support_calls"] / 10) * 0.4
        + (1 - data["tenure_months"] / 72) * 0.3
    )
    data["churn"] = (np.random.random(n_samples) < churn_prob).astype(int)

    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_PATH, index=False)

    # Print drift summary
    original_monthly_mean = (20 + 120) / 2  # ~70
    drifted_monthly_mean = df["monthly_charges"].mean()

    original_calls_mean = 10 / 2  # ~5
    drifted_calls_mean = df["num_support_calls"].mean()

    original_tenure_mean = (1 + 72) / 2  # ~36.5
    drifted_tenure_mean = df["tenure_months"].mean()

    print("\n╔══════════════════════════════════════════════════╗")
    print("║   🔀 Drift Simulator — Production Data Shifted   ║")
    print("╚══════════════════════════════════════════════════╝\n")
    print(f"  Generated {len(df)} drifted samples → {OUTPUT_PATH.name}\n")
    print(f"  📈 Monthly Charges:   ${original_monthly_mean:.0f} → ${drifted_monthly_mean:.0f}  (↑ {((drifted_monthly_mean/original_monthly_mean)-1)*100:.0f}%)")
    print(f"  📈 Support Calls:     {original_calls_mean:.1f} → {drifted_calls_mean:.1f}  (↑ {((drifted_calls_mean/original_calls_mean)-1)*100:.0f}%)")
    print(f"  📉 Tenure (months):   {original_tenure_mean:.1f} → {drifted_tenure_mean:.1f}  (↓ {((1 - drifted_tenure_mean/original_tenure_mean))*100:.0f}%)")
    print(f"  📊 Churn Rate:        {df['churn'].mean():.1%}")
    print(f"\n  Next: Run 'python monitoring/monitor.py' to see drift detected!\n")


if __name__ == "__main__":
    generate_drifted_data()
