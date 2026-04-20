import sys
import json
import subprocess

def load_json(filepath):
    with open(filepath, "r") as f:
        return json.load(f)

def load_git_json(commit, filepath):
    try:
        # Read the file contents from the specified git commit
        output = subprocess.check_output(["git", "show", f"{commit}:{filepath}"], stderr=subprocess.STDOUT)
        return json.loads(output.decode('utf-8'))
    except subprocess.CalledProcessError:
        # File might not exist in the previous commit
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python evaluate_metrics.py <threshold_percent>")
        sys.exit(1)

    try:
        threshold_percent = float(sys.argv[1])
    except ValueError:
        print("Threshold must be a number.")
        sys.exit(1)

    print(f"Evaluating Model Performance Drop (Threshold: {threshold_percent}%)")

    # The new metrics are currently on disk
    try:
        new_metrics = load_json("metrics.json")
    except FileNotFoundError:
        print("Error: metrics.json not found on disk.")
        sys.exit(1)

    # The old metrics are currently committed in HEAD
    old_metrics = load_git_json("HEAD", "metrics.json")

    if old_metrics is None:
        print("No previous metrics.json found in git. First run, so passing automatically.")
        sys.exit(0)

    print(f"Old Metrics: {old_metrics}")
    print(f"New Metrics: {new_metrics}")

    # Check metrics (assuming higher is better, like accuracy and auc_roc)
    failed = False
    for metric_name in new_metrics:
        if metric_name in old_metrics:
            old_val = float(old_metrics[metric_name])
            new_val = float(new_metrics[metric_name])

            if old_val > 0:
                drop_percent = ((old_val - new_val) / old_val) * 100
                print(f"Metric '{metric_name}': Old={old_val:.4f}, New={new_val:.4f} -> Drop: {drop_percent:.2f}%")
                
                if drop_percent > threshold_percent:
                    print(f"❌ '{metric_name}' dropped by more than {threshold_percent}%!")
                    failed = True
            else:
                print(f"Metric '{metric_name}': Old={old_val:.4f}, New={new_val:.4f} (baseline was 0, cannot calculate drop)")

    if failed:
        print("\n❌ CI/CD Rollback Triggered: New model performance is significantly worse than the previous baseline.")
        sys.exit(1)
    else:
        print("\n✅ New model performance is within acceptable thresholds.")
        sys.exit(0)

if __name__ == "__main__":
    main()
