# Realtime MLOps Pipeline: Customer Churn Predictor 

A fully automated, production-grade MLOps demonstration for a customer churn prediction model. This project leverages **Azure Blob Storage** for artifact storage, **DVC** for data and metrics versioning, **GitHub Actions** for CI/CD, **ArgoCD** for GitOps deployments, and **KServe** for serverless ML inference.

---

## 📍 Table of Contents
- [What Does This Model Do?](#-what-does-this-model-do)
- [Architecture At A Glance](#-architecture-at-a-glance)
- [Project Structure](#-project-structure)
- [Security & Secrets Setup](#-security--secrets-setup-kubernetes)
- [Prerequisites](#-prerequisites)
- [MLOps Pipeline Steps](#-mlops-pipeline-steps)
- [Test KServe Inference Live](#-test-kserve-inference-live)
- [ArgoCD Setup](#-argocd-gitops)
- [ChurnShield UI (Frontend)](#-churnshield-ui-frontend)
- [Monitoring Infrastructure](#-monitoring-infrastructure)
- [Workflow Trace](#-complete-mlops-workflow-trace)

---

## What Does This Model Do?

**Real-World Example:**

Imagine you run a telecom company with thousands of customers. Some customers are happy and stay for years, while others leave (churn) after a few months. This model predicts which customers are likely to leave.

**Example Customer:**
- **Sarah** is 45 years old
- Been a customer for 24 months
- Pays $79.99/month
- Total spent: $1,920
- Called customer support 3 times this month

**Model Prediction:**
```json
{
  "churn": 1,
  "churn_probability": 0.73
}
```

**Translation:** Sarah has a **73% chance of canceling her subscription**. The model flags her so the business can proactively offer a discount or personalized support before she leaves.

**The model looks at patterns like:**
- High monthly charges → More likely to churn
- More support calls → Customer is frustrated
- Low tenure → Haven't built loyalty yet

---

## 🚀 Architecture At A Glance

1. **Source of Truth (Git):** Code, hyperparameters (`params.yaml`), and GitOps configurations live here.
2. **Data Ledger (DVC):** Tracks massive datasets, binaries, and training metrics (`metrics.json`). Artifacts are pushed to Azure Blob Storage using cryptographic hashes.
3. **Continuous Integration (GitHub Actions):** Automatically runs `dvc repro` on code push, pushes new models to Azure, and updates Kubernetes definitions with the newest model URIs.
4. **Continuous Deployment (ArgoCD):** Watches the Git repository for updated Kubernetes definitions. Triggers KServe to spin up new endpoints with zero downtime.
5. **Secure Inference Engine (KServe):** 
    - **Shell-Wrapped Loader**: Uses a custom initContainer to dynamically pull binaries from Azure while managing Kubernetes Secrets.
    - **Secret-Based Auth**: Securely stores SAS tokens in **Kubernetes Secrets** (`az-secret`).
    - **Custom Domain**: Served on `mlops-demo.labs.csi-infra.com` via Nginx Ingress.

### System Diagram
```mermaid
flowchart TD
  subgraph Dev["Version Control & Storage"]
    Git("GitHub (Code & Manifests)")
    Azure("Azure Blob (DVC Models)")
  end

  subgraph CI["Continuous Integration"]
    GHA("GitHub Actions Pipeline")
  end

  subgraph Cluster["Kubernetes (KIND)"]
    subgraph ArgoCD["GitOps"]
      Argo("ArgoCD Controller")
    end
    subgraph KServe["Inference"]
      ISVC["KServe InferenceService"]
      Pod["Model Predictor Pod"]
    end
  end

  Developer((Developer)) -->|"git push"| Git
  Git --> GHA
  GHA -->|"retrains & pushes"| Azure
  GHA -->|"commits URI"| Git
  Argo -.->|"watches"| Git
  Argo -->|"deploys"| ISVC
  ISVC -->|"loads model"| Azure
```

---

## 📁 Project Structure

```text
churn-model/
├── params.yaml                   # Centralized Hyperparameters & Data Configs
├── generate_data.py              # Generate synthetic churn dataset
├── train.py                      # Train the RandomForest model
├── api.py                        # FastAPI local inference server
├── requirements.txt              # Python dependencies
├── metrics.json                  # Model accuracy and AUC-ROC (Tracked by DVC)
├── Dockerfile                    # Container image for local FastAPI
├── Dockerfile.kserve             # Custom KServe SKLearn server image
├── dvc.yaml & dvc.lock           # DVC pipeline stages and lockfiles
├── .dvc/config                   # DVC remote config (Azure Blob)
├── models/
│   └── churn_model.pkl           # Trained model (uploaded to Azure)
├── data/
│   └── churn_data.csv            # Synthetic churn dataset (tracked by DVC)
├── k8s/
│   ├── serviceaccount.yaml       # Namespace, Secrets, and ServiceAccount
│   ├── inference.yaml            # KServe InferenceService (Shell-Wrapped)
│   ├── inferenceservice-config.yaml # Global KServe networking config (Custom Domain)
│   ├── ui.yaml                   # ChurnShield UI Deployment, Service & PVC
│   └── monitoring/
│       ├── prometheus.yaml       # Prometheus Namespace, ConfigMap, Deployment, Service & PVC
│       └── grafana.yaml          # Grafana ConfigMap (datasource+dashboard), Deployment, Service & PVC
├── monitoring/
│   ├── monitor.py                # Evidently AI report generator (3 reports)
│   ├── simulate_drift.py         # Synthetic drift data generator for demos
│   ├── drifted_data.csv          # Auto-generated drifted dataset (created by simulate_drift.py)
│   └── reports/                  # Output folder for generated HTML reports
│       ├── data_drift_report.html
│       ├── model_performance_report.html
│       └── data_quality_report.html
├── ui/
│   ├── index.html                # ChurnShield AI — Main Demo Frontend
│   ├── monitoring.html           # Embedded Evidently Reports Dashboard
│   ├── architecture.html         # In-browser Architecture diagram page
│   ├── server.py                 # Python proxy server & Prometheus metrics endpoint
│   └── Dockerfile.ui             # Container image for the UI + Monitoring suite
├── .github/workflows/
│   └── main.yml                  # GitHub Actions CI/CD pipeline
└── argocd/
    └── application.yaml          # ArgoCD GitOps application
```

---

## 🔐 Security & Secrets Setup (Kubernetes)

This project storing SAS tokens on **Kubernetes Secrets**.

### Create the Azure Secret
Before deploying, create a secret named `az-secret` in the `churn-model` namespace containing your Azure Connection String:

```bash
kubectl create namespace churn-model
kubectl create secret generic az-secret \\
  --from-literal=AZURE_STORAGE_CONNECTION_STRING='your_connection_string_here' \\
  -n churn-model
```

*Note: The KServe pod uses the `sa-az-access` ServiceAccount to grant the model loader access to this secret.*

---

## 🛠 Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.11+ | Running training and API scripts |
| Docker | Building container images |
| kubectl | Interacting with Kubernetes |
| kind | Running a local Kubernetes cluster |
| Azure CLI (`az`) | Managing Azure Blob Storage |
| Azure Storage Account | `storageaccountmlopspoc` with container `models-container` |
| GitHub Repository | For CI/CD via GitHub Actions |

---

## ⚙️ MLOps Pipeline Steps

### 1. Local Setup & Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run DVC to generate synthetic datasets and train the model automatically
dvc repro

# Test API locally
python api.py
# Visit http://localhost:8000/docs
```

### 2. 🧪 Local DVC Features & Experiment Tracking

DVC acts as a smart cache and an experiment auditor natively integrated with Git.

#### The Smart Cache
If you run `dvc repro` twice without changing code/parameters, DVC skips computation (`Data and pipelines are up to date`), saving cloud compute costs.

#### The Metrics Diff
Open `params.yaml`, change the `n_estimators`, and run `dvc repro`. Use `dvc metrics diff` to see instantly how your Accuracy and AUC-ROC shifted before committing to Git!
```bash
# Example output:
# Path          Metric    Old      New      Change
# metrics.json  accuracy  0.79155  0.81234  0.02079
# metrics.json  roc_auc   0.84112  0.86543  0.02431
dvc metrics diff
```

#### ⏪ The Time Machine (Rollback Data & Model)
To restore a bad model state locally for debugging, simply checkout the old git commit and pull the old data/model artifacts using DVC:
```bash
# 1. Checkout the previous known good commit
git checkout <old-commit-hash>

# 2. Pull the exact datasets and model binaries for that commit
dvc pull
```

#### 🔄 GitOps Production Rollback
Because ArgoCD manages our cluster based on Git, rolling back production is as simple as reverting the commit that broke it.
```bash
# Revert the bad commit in Git
git revert <bad-commit-hash>
git push origin main

# ArgoCD will automatically detect the reverted state and deploy the old model!
```

### 3. GitHub Actions CI/CD

The pipeline runs automatically on push to `main`. It achieves "Invisible MLOps":
1. Triggers DVC pipeline dynamically reading from Azure Connection Strings
2. **Automated Pre-Deployment Rollback**: Evaluates new model metrics (`metrics.json`) against the previous commit. If performance drops by >5%, the pipeline fails instantly, aborting the rollout to protect production.
3. Uploads updated DVC storage chunks safely (Hashes logic)
4. Uploads raw .pkl securely directly to the Azure KServe path using Git SHAs
5. Updates `k8s/inference.yaml` storageUri securely via Python `update_yaml.py`
6. Commits `dvc.lock`, `metrics.json` and the YAML updates back automatically.

### 4. Kubernetes with KIND & KServe

```bash
# Create cluster
kind create cluster --name churn-model

# Install KServe
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml

# Install Ingress Nginx (Required for local custom domains)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Map the domain (on your host machine)
echo "127.0.0.1 mlops-demo.labs.csi-infra.com" | sudo tee -a /etc/hosts
echo "127.0.0.1 churn-predictor-churn-model.mlops-demo.labs.csi-infra.com" | sudo tee -a /etc/hosts
```

### 5. Deploy the Inference Service

```bash
# Apply namespace, secret, and service account
kubectl apply -f k8s/serviceaccount.yaml

# Deploy the KServe inference service
kubectl apply -f k8s/inference.yaml

# Watch until READY = True
kubectl get inferenceservice churn-predictor -n churn-model -w
```
> **KServe Azure Authentication Note:** KServe downloads the model from Azure Blob using the Kubernetes secret referenced by the ServiceAccount (`sa-az-access` / `az-secret`).

### 6. Test KServe Inference Live

Both methods require the correct **5-feature set**: `age`, `tenure_months`, `monthly_charges`, `total_charges`, `num_support_calls`.

#### Localhost Testing (Port-Forwarding)
```bash
# Terminal 1: Port-forward ingress

nohup kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 10000:80 > /tmp/ingress-forward.log 2>&1 &

# Terminal 2: Prediction via Localhost (using Host header)
# Test prediction (sklearn expects data as an ordered array)
# Order: age, tenure_months, monthly_charges, total_charges, num_support_calls

curl -X POST http://churn-predictor-churn-model.mlops-demo.labs.csi-infra.com:10000/v1/models/churn-predictor:predict \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      [45, 24, 79.99, 1920.00, 3]
    ]
  }'

OR 

nohup kubectl port-forward -n churn-model service/churn-predictor-predictor 8000:80 > /tmp/churn-forward.log 2>&1 &

curl -X POST http://localhost:8000/v1/models/churn-predictor:predict \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      [45, 24, 79.99, 1920.00, 3]
    ]
  }'
```


### 7. ArgoCD (GitOps)

ArgoCD watches the Git repository for changes to `k8s/inference.yaml` and automatically deploys the latest model to Kubernetes.

```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s

# Deploy the ArgoCD application (points to this repo)
kubectl apply -f argocd/application.yaml

# Access ArgoCD UI (visit https://localhost:8080)
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

---

## 🖥️ ChurnShield UI (Frontend)

**ChurnShield AI** is a responsive, production-quality demo dashboard that lets you visually test the churn prediction model through a browser. It features animated input sliders, a risk gauge, and AI-generated retention recommendations.

### How it works

Because browsers block cross-origin requests (CORS), the frontend uses a lightweight **Python proxy server** that:
1. Serves the UI at `http://localhost:5000`
2. Forwards `/predict` requests server-side to KServe (bypassing CORS restrictions)
3. Exposes a `/metrics` endpoint for Prometheus scraping
4. Runs `monitoring/monitor.py` and `monitoring/simulate_drift.py` on-demand via API

> **Architecture Note**: The UI proxy server (`ui/server.py`) is deployed as a Kubernetes `Deployment` (`k8s/ui.yaml`). It is backed by a **Horizontal Pod Autoscaler (HPA)** that scales replicas up to 3 during traffic spikes (CPU > 70%), ensuring high availability. Metrics persist across restarts via `PersistentVolumeClaim`.

### Initial Deployment (First Time Only)

```bash
# 1. Build the Docker image
docker build -t churnshield-ui:latest -f ui/Dockerfile.ui .

# 2. Load it into the KIND cluster (KIND cannot pull from Docker Hub by default)
kind load docker-image churnshield-ui:latest --name churn-model

# 3. Deploy the UI, Service, and PVC
kubectl apply -f k8s/ui.yaml

# 4. Verify the pod is running
kubectl get pods -n monitoring -l app=churnshield-ui
```

### Accessing the UI

After deployment, use `kubectl port-forward` to expose the UI on your local machine:

```bash
nohup kubectl port-forward --address 0.0.0.0 -n monitoring svc/churnshield-ui 5000:5000 > /tmp/ui-forward.log 2>&1 &
```

Then open: `http://localhost:5000` (or `http://churnshield.mlops-demo.labs.csi-infra.com:5000` if you have the custom domain configured)

### Rebuilding After Code Changes

If you change `ui/server.py`, `ui/index.html`, or `monitoring/monitor.py`:

```bash
docker build -t churnshield-ui:latest -f ui/Dockerfile.ui . && \
kind load docker-image churnshield-ui:latest --name churn-model && \
kubectl rollout restart deployment churnshield-ui -n monitoring
```

### Demo Scenarios

| Customer Type | Age | Tenure | Monthly $ | Total $ | Calls | Expected Result |
|---|---|---|---|---|---|---|
| Happy long-term | 55 | 48 | 35 | 1680 | 0 | 🟢 Low Risk |
| New struggling | 28 | 3 | 120 | 360 | 10 | 🔴 High Risk |
| At-risk mid-tier | 40 | 12 | 90 | 1080 | 2 | ⚠️ Medium Risk |

> **Note:** The UI displays a risk probability percentage derived from the input features as a visual enhancement for demos, since the standard KServe SKLearn server returns binary predictions (0 or 1).

---

## 📈 Monitoring Infrastructure

ChurnShield uses a **dual-layer monitoring system**: operational infrastructure monitoring via Prometheus & Grafana, and ML-specific health monitoring via Evidently AI. All components run as Kubernetes pods in the `monitoring` namespace.

---

### 1. Operations Monitoring (Prometheus & Grafana)

Tracks every inference request in real time: counts, latency, errors, and churn vs. retained distribution.

#### Kubernetes Manifests

| File | What It Creates |
|------|-----------------|
| `k8s/monitoring/prometheus.yaml` | `monitoring` namespace, Prometheus `ConfigMap` (scrape config), `Deployment` (v2.51.0), `Service` (ClusterIP:9090), and 5Gi `PersistentVolumeClaim` for metric history |
| `k8s/monitoring/grafana.yaml` | Grafana `Deployment` (v10.4.1), pre-built dashboard `ConfigMap`, datasource `ConfigMap`, 2Gi `PersistentVolumeClaim` for dashboard persistency, and `Service` (ClusterIP:3000) |

#### How Prometheus Scrapes the UI

Prometheus is configured (in `prometheus.yaml`) to scrape the ChurnShield UI pod at:
```
http://churnshield-ui.monitoring.svc.cluster.local:5000/metrics
```
Every **10 seconds**, it pulls counters and histograms from the `prometheus_client` library embedded in `ui/server.py`.

#### Prometheus Metrics Exposed

The following custom metrics are emitted by `ui/server.py`:

| Metric | Type | Description |
|--------|------|-------------|
| `churnshield_prediction_requests_total` | Counter | Total predictions, labelled by `result` (`churn` / `no_churn`) |
| `churnshield_prediction_latency_seconds` | Histogram | End-to-end KServe round-trip latency (buckets: 0.05s → 10s) |
| `churnshield_prediction_errors_total` | Counter | Failed prediction requests (network errors, KServe timeouts, etc.) |

#### Grafana Dashboard — ChurnShield AI Inference Monitoring

The pre-built dashboard (`grafana-dashboard-churnshield` ConfigMap in `grafana.yaml`) loads automatically at `http://localhost:3000`. It contains **7 panels**:

| Panel | Type | What It Shows |
|-------|------|---------------|
| 🔮 Prediction Requests / min | Time Series | Rate of churn vs. no_churn predictions over time (`rate(...[1m])`) |
| ⏱️ Prediction Latency (p50/p95/p99) | Time Series | KServe response time percentiles over a 5-minute window |
| 📊 Total Predictions | Stat (Big Number) | Cumulative prediction count since deployment |
| 🔴 Churn Predictions | Stat (Big Number) | Count of customers flagged as likely to churn |
| 🟢 Retained Predictions | Stat (Big Number) | Count of customers predicted as retained |
| ❌ Errors | Stat (Big Number) | Count of failed inference requests |
| 📈 Churn vs Retained Ratio | Donut Chart | Split of all predictions by result label |
| ⏱️ Average Latency | Gauge (0-5s) | Rolling average latency with green/amber/red thresholds |

**Setup & Access:**
```bash
# Deploy Prometheus and Grafana
kubectl apply -f k8s/monitoring/

# Port-forward Grafana and Prometheus
nohup kubectl port-forward -n monitoring svc/grafana 3000:3000 > /tmp/grafana-forward.log 2>&1 &
nohup kubectl port-forward -n monitoring svc/prometheus 9090:9090 > /tmp/prometheus-forward.log 2>&1 &
```
- **Access Grafana**: `http://localhost:3000` (Login: `admin` / `admin`)
- **Access Alerts**: `http://localhost:9090/alerts`

#### Prometheus Alerting Rules
The `prometheus.yaml` config includes built-in alerting rules to detect degradation before it impacts users. You can view their status at the Prometheus URL above.
* **`InstanceDown`**: Fires if the UI proxy pod fails to respond to scrapes for 1 minute (Critical).
* **`HighErrorRate`**: Fires if >5% of inference requests fail over a 1-minute window (Warning).
* **`HighLatency`**: Fires if the 99th percentile (p99) latency exceeds 2 seconds for 2 continuous minutes (Warning).

> **Metrics Persistence:** Prometheus metric data is stored on a `prometheus-storage-pvc` (5Gi PVC). Grafana dashboards and settings are stored on `grafana-storage-pvc` (2Gi PVC). Both survive pod restarts.

---

### 2. ML System Monitoring (Evidently AI)

Tracks data drift, prediction drift, and model quality by comparing the **70% training split (reference)** against **30% production split (current)** — or against drifted data when drift simulation is active.

#### Scripts

| File | Purpose |
|------|---------|
| `monitoring/monitor.py` | Generates 3 Evidently HTML reports and a `summary.json` |
| `monitoring/simulate_drift.py` | Generates synthetic `drifted_data.csv` with realistic distribution shifts |
| `monitoring/drifted_data.csv` | Auto-generated — created by `simulate_drift.py`, deleted to reset baseline |
| `monitoring/reports/` | Output folder for the 3 HTML report files |

#### What `monitor.py` Generates

| Report File | What It Covers |
|-------------|----------------|
| `data_drift_report.html` | Per-feature drift scores for all 5 input features + prediction drift. Uses statistical tests to detect distribution shifts (e.g. `monthly_charges` increasing significantly after drift simulation). |
| `model_performance_report.html` | Classification metrics: Accuracy, Precision, Recall, F1, ROC-AUC, Confusion Matrix — comparing training (reference) performance versus current production behavior. |
| `data_quality_report.html` | Missing values, feature ranges, value counts, and overall dataset statistics for both reference and current datasets side-by-side. |

#### What `simulate_drift.py` Does

Generates `monitoring/drifted_data.csv` with **three deliberate distribution shifts** to simulate a real production degradation scenario:

| Feature | Original Range | Drifted Range | Simulated Scenario |
|---------|---------------|---------------|--------------------|
| `monthly_charges` | $20–$120 (avg ~$70) | $50–$180 (avg ~$115) | Price increase — 64% higher bills |
| `num_support_calls` | 0–10 (avg 5.0) | 2–15 (avg ~8.1) | Service quality drop — 61% more support calls |
| `tenure_months` | 1–72 (avg ~36) | 1–30 (avg ~15) | Influx of new short-tenure customers — 59% drop |
| `churn` rate | ~35% baseline | ~83% in drifted set | Model would now assign high-risk to most customers |

#### Demo Workflow — Detect Drift End-to-End

```bash
# Step 1: Generate baseline report (no drift)
#   → In the browser: click "Generate Report" in the Monitoring tab
#   OR directly:
python monitoring/monitor.py

# Step 2: Simulate production drift
#   → In the browser: click "Simulate Drift" button in the Monitoring tab
#   OR directly:
python monitoring/simulate_drift.py

# Step 3: Re-generate report to detect drift
python monitoring/monitor.py

# Step 4: View the drift reports
#   → Open: http://localhost:5000/monitoring

# Step 5: Reset to baseline (remove drifted data)
rm monitoring/drifted_data.csv
```

#### Accessing Evidently Reports via the UI

The ChurnShield UI at `http://localhost:5000/monitoring` embeds all 3 HTML reports in an iframe dashboard. The following API endpoints are available from the browser:

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `POST /run-monitoring` | POST | Triggers `monitor.py` inside the container, generates all 3 reports |
| `POST /simulate-drift` | POST | Triggers `simulate_drift.py`, creates `drifted_data.csv` |
| `GET /report/<filename>` | GET | Serves individual HTML report files |
| `GET /metrics` | GET | Returns raw Prometheus metrics text |
| `POST /predict` | POST | Proxies the request to KServe and returns prediction |


---

## 🔁 Complete MLOps Workflow Trace

- [ ] **Developer** pushes code/parameters to GitHub (main branch)
- [ ] **GitHub Actions Pipeline** triggers:
  - [ ] Recomputes cached Data Logic (DVC)
  - [ ] Retrains model using parameters / metrics (`churn_model.pkl`)
  - [ ] Uploads hashes privately → Azure Blob Storage
  - [ ] Uploads raw `.pkl` securely to Azure via Git SHA path
  - [ ] Updates `k8s/inference.yaml` storageUri via `update_yaml.py`
  - [ ] Commits `metrics.json` and `dvc.lock` back into Git
- [ ] **ArgoCD** detects change in `k8s/inference.yaml`
- [ ] **ArgoCD** syncs state → applies changes to Kubernetes
- [ ] **KServe** securely loads model from Azure using `az-secret`
- [ ] **KServe** serves predictions via Custom Domain on Nginx Ingress

---

## 🛠 Local API Usage (`api.py`)

If you are running the FastAPI server locally (outside of Kubernetes) for rapid development:

```bash
# Start the local server
python api.py

# Send a test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "age": 45,
    "tenure_months": 24,
    "monthly_charges": 79.99,
    "total_charges": 1920.00,
    "num_support_calls": 3
  }'
```

---

## 📊 Key Components Summary

| Component | Role / Purpose |
|-----------|----------------|
| **Azure Blob Storage** | Persistent Model Registry (`storageaccountmlopspoc`) |
| **DVC** | Data & Model versioning/tracking |
| **GitHub Actions** | CI/CD — Automation of training and manifest updates |
| **KServe** | Serverless ML Inference & Auto-scaling |
| **ArgoCD** | GitOps Managed Lifecycle & Drift Detection |
| **Kubernetes Secrets** | Secure Credential Management (`az-secret`) |
| **Ingress Nginx** | Traffic Routing for `mlops-demo` Custom Domain |
| **KIND / Minikube** | Local Kubernetes Infrastructure |
| **ChurnShield UI** | Browser-based Demo Frontend — Dockerized & deployed in Kubernetes (`k8s/ui.yaml`) |
| **Prometheus & Grafana** | Operations Monitoring (Latency, Requests, Errors) |
| **Evidently AI** | ML Monitoring (Data/Prediction Drift & Model Quality) |

---

## 🔄 After Laptop Restart — Quick-Start Commands

After a system reboot, the KIND cluster and all pods will still be running (KIND persists across reboots), but `kubectl port-forward` processes do not survive reboots. Run these commands to restore full functionality:

```bash
# 1. Expose the ChurnShield UI on port 5000 (required for the browser)
nohup kubectl port-forward --address 0.0.0.0 -n monitoring svc/churnshield-ui 5000:5000 > /tmp/ui-forward.log 2>&1 &

# 2. Expose Grafana on port 3000 (optional — for monitoring dashboard)
nohup kubectl port-forward -n monitoring svc/grafana 3000:3000 > /tmp/grafana-forward.log 2>&1 &

# 3. Expose Prometheus on port 9090 (optional — for viewing Active Alerts)
nohup kubectl port-forward -n monitoring svc/prometheus 9090:9090 > /tmp/prometheus-forward.log 2>&1 &

# 4. Expose Ingress on port 10000 (optional — for direct KServe curl testing)
nohup kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 10000:80 > /tmp/ingress-forward.log 2>&1 &

# 5. Expose ArgoCD on port 9000 (optional — for GitOps dashboard)
nohup kubectl port-forward svc/argocd-server -n argocd 9000:443 > /tmp/argocd-forward.log 2>&1 &
```

> **Tip:** Run all of these in one shot by pasting all commands together. They all run in the background via `nohup` so your terminal stays free.

### Verifying Everything is Healthy

```bash
# Check all pods are Running
kubectl get pods -n monitoring
kubectl get pods -n churn-model
kubectl get pods -n argocd

# Quick prediction test
curl -s -X POST http://127.0.0.1:5000/predict \
  -H "Content-Type: application/json" \
  -d '{"instances": [[45, 24, 79.99, 1920.00, 3]]}'
# Expected: {"predictions": [1]}

# Check metrics are being collected
curl -s http://127.0.0.1:5000/metrics | grep churnshield_prediction_requests_total
```

---

## 📝 Notes
- `k8s/inference.yaml` points to the Azure Blob model path (no SAS embedded). Regenerate/update your Azure connection string secret in Kubernetes if credentials change.
- `k8s/serviceaccount.yaml` references the Kubernetes secret (`az-secret`) used by KServe to download from Azure Blob.
- This is a demo project — production setups require monitoring, logging, secret rotation, and security hardening.
