# Realtime MLOps Pipeline: Customer Churn Predictor 

A fully automated, production-grade MLOps demonstration for a customer churn prediction model. This project leverages **Azure Blob Storage** for artifact storage, **DVC** for data and metrics versioning, **GitHub Actions** for CI/CD, **ArgoCD** for GitOps deployments, and **KServe** for serverless ML inference.

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
5. **Inference Engine (KServe):** Pulls the binary model securely from Azure via SAS tokens and serves a lightning-fast REST API.

---

## 📁 Project Structure

```text
churn-model/
├── params.yaml                   # Centralized Hyperparameters & Data Configs
├── generate_data.py              # Generate synthetic churn dataset
├── train.py                      # Train the RandomForest model
├── api.py                        # FastAPI local inference server
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image for KServe
├── dvc.yaml & dvc.lock           # DVC pipeline stages and lockfiles
├── metrics.json                  # Model accuracy and AUC-ROC (Tracked by DVC)
├── .dvc/config                   # DVC remote config (Azure Blob)
├── models/
│   └── churn_model.pkl           # Trained model (uploaded to Azure)
├── k8s/
│   ├── serviceaccount.yaml       # Kubernetes namespace, secret & service account
│   └── inference.yaml            # KServe InferenceService definition
├── .github/workflows/
│   └── main.yml                  # GitHub Actions CI/CD pipeline
└── argocd/
    └── application.yaml          # ArgoCD GitOps application
```

---

## 🛠 Prerequisites

Before running this project, ensure you have the following ready:

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

## 🔐 Azure Blob & GitHub Secrets Setup

This project uses **Azure Blob Storage** to store trained models and DVC tracking artifacts.

In production/demo usage, you only need the **Azure connection string** in two places:
1. **GitHub Actions** — `AZURE_STORAGE_CONNECTION_STRING` is used to run `dvc pull/repro/push` and to upload the trained model blob during CI.
2. **KServe** — the model download during pod init uses Kubernetes Secret `az-secret` (referenced by `sa-az-access`), which must contain `AZURE_STORAGE_CONNECTION_STRING`.

> Generate the Azure **connection string** from your Storage Account in the Azure Portal and use it as `AZURE_STORAGE_CONNECTION_STRING`.

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

### 2. 🧪 Local DVC Features (Experiment Tracking)

DVC acts as a smart cache and an experiment auditor natively integrated with Git.

*   **The Smart Cache:** If you run `dvc repro` twice without changing code/parameters, DVC skips computation (`Data and pipelines are up to date`), saving cloud compute costs.
*   **The Metrics Diff:** Open `params.yaml`, change the `n_estimators`, and run `dvc repro`. Use `dvc metrics diff` to see instantly how your Accuracy and AUC-ROC shifted before committing to Git!
*   **The Time Machine:** To restore a bad model state simply `git checkout <old-commit-hash>` followed by `dvc pull` to bring back exact dataset states locally without relying on bulky Git LFS.

### 3. GitHub Actions CI/CD

The pipeline runs automatically on every push to `main`. It achieves "Invisible MLOps":
1. Triggers DVC pipeline dynamically reading from Azure Connection Strings
2. Uploads updated DVC storage chunks safely (Hashes logic)
3. Uploads `models/churn_model.pkl` explicitly to the Azure Blob KServe path using Git SHAs
4. Updates `k8s/inference.yaml` securely with the latest storage URI/path (no SAS token in Git)
5. Commits `dvc.lock`, `metrics.json` and the YAML updates back automatically (triggering ArgoCD).

### 4. Kubernetes with KIND (Local Cluster) & KServe

```bash
# Create a local KIND cluster
kind create cluster --name churn-model

# Install KServe (includes cert-manager, Istio, etc.)
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml

# Wait for KServe controller to be ready
kubectl wait --for=condition=ready pod -l control-plane=kserve-controller-manager -n kserve --timeout=120s
```

### 5. Deploy the Inference Service

**Important:** Ensure `k8s/inference.yaml` points to the correct model path in Azure Blob (no SAS token embedded). Also ensure `k8s/serviceaccount.yaml` has your `AZURE_STORAGE_CONNECTION_STRING` injected into Kubernetes secrets so KServe can download the model.

```bash
# Apply namespace, secret, and service account
kubectl apply -f k8s/serviceaccount.yaml

# Deploy the KServe inference service
kubectl apply -f k8s/inference.yaml

# Watch until READY = True (may take 2-3 minutes)
kubectl get inferenceservice churn-predictor -n churn-model -w
```
> **KServe Azure Authentication Note:** KServe downloads the model from Azure Blob using the Kubernetes secret referenced by the ServiceAccount (`sa-az-access` / `az-secret`).

### 6. Test KServe Inference Live

```bash
# Port-forward the inference service locally
kubectl port-forward -n churn-model service/churn-predictor-predictor 8080:80

# Test prediction (sklearn expects data as an ordered array)
# Order: age, tenure_months, monthly_charges, total_charges, num_support_calls
curl -X POST http://localhost:8080/v1/models/churn-predictor:predict \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [
      [45, 24, 79.99, 1920.00, 3]
    ]
  }'
```

Expected response:
```json
{
  "predictions": [1]
}
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

## 🔁 Complete MLOps Workflow Trace

```
Developer pushes code/parameters to GitHub (main branch)
        │
        ▼
GitHub Actions Pipeline
  ├── Recomputes cached Data Logic (DVC)
  ├── Retrains model using parameters / metrics (churn_model.pkl)
  ├── Uploads hashes privately → Azure Blob Storage
  ├── Uploads raw .pkl securely directly to KServe container
  ├── Updates k8s/inference.yaml storageUri securely via Python update_yaml.py
  └── Commits metrics.json and dvc.lock mapping back into Git!
        │
        ▼
ArgoCD detects change in tracked k8s/inference.yaml
        │
        ▼
ArgoCD syncs → applies state to Kubernetes
        │
        ▼
KServe securely streams model binary from Azure Blob using Kubernetes-provided Azure credentials
        │
        ▼
KServe serves updated predictions via REST API without downtime
```

---

## Local API Usage (FastAPI `api.py`)

If running isolated code directly:

```bash
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

Response:
```json
{
  "churn": 1,
  "churn_probability": 0.73
}
```

---

## Key Components Summary

| Component | Role |
|-----------|------|
| **Azure Blob Storage** | Remote storage for trained model (`storageaccountmlopspoc`) |
| **DVC** | Model versioning and tracking (remote: Azure Blob) |
| **GitHub Actions** | CI/CD — trains, uploads, and updates deployment YAML |
| **KServe** | Serverless ML inference on Kubernetes |
| **KIND** | Local Kubernetes cluster for testing |
| **ArgoCD** | GitOps — auto-deploys when `inference.yaml` changes |

---

## Notes
- `k8s/inference.yaml` points to the Azure Blob model path (no SAS embedded). Regenerate/update your Azure connection string secret in Kubernetes if credentials change.
- `k8s/serviceaccount.yaml` references the Kubernetes secret (`az-secret`) used by KServe to download from Azure Blob.
- This is a demo project — production setups require monitoring, logging, secret rotation, and security hardening.
