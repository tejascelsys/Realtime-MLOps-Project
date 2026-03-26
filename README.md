# Churn Model MLOps Demo

A demonstration of MLOps practices for a customer churn prediction model, using Azure Blob Storage for model storage, KServe for inference, GitHub Actions for CI/CD, and ArgoCD for GitOps deployment.

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

## Project Structure

```
churn-model/
├── generate_data.py              # Generate synthetic churn dataset
├── train.py                      # Train the RandomForest model
├── api.py                        # FastAPI local inference server
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image for KServe
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

## Prerequisites

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

## Azure Blob Storage Setup

This project uses **Azure Blob Storage** (account: `storageaccountmlopspoc`, container: `models-container`) to store trained models.

### Generate a SAS Token

A SAS (Shared Access Signature) token is required in two places:
1. **GitHub Actions** — to upload the model blob during CI.
2. **KServe** — embedded in the `storageUri` to download the model at inference time.

**Steps to generate a SAS token in the Azure Portal:**
1. Go to your Storage Account → **Shared access signature** (under Security + networking).
2. Under **Allowed services**, check ✅ **Blob**.
3. Under **Allowed resource types**, check ✅ **Container** and ✅ **Object** (both required).
4. Under **Allowed permissions**, check: Read, Write, Create, Add, List.
5. Set an expiry date (e.g. 1 year from today).
6. Click **Generate SAS and connection string**.
7. Copy the **Connection string** — this is your `AZURE_STORAGE_CONNECTION_STRING`.
8. Copy the **SAS token** query string (starting with `sv=...`) — this is embedded in `inference.yaml`.

> **Note:** The SAS connection string format looks like:
> `BlobEndpoint=https://storageaccountmlopspoc.blob.core.windows.net/;...;SharedAccessSignature=sv=...`

---

## MLOps Pipeline Steps

### 1. Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic dataset
python generate_data.py

# Train model (saves to models/churn_model.pkl)
python train.py

# Test API locally
python api.py
# Visit http://localhost:8000/docs
```

### 2. GitHub Actions CI/CD

The pipeline runs automatically on every push to `main`. It:
1. Generates the dataset
2. Trains the model
3. Uploads `models/churn_model.pkl` to Azure Blob Storage (`models-container/models/`)
4. Updates `k8s/inference.yaml` with the latest storage URI
5. Commits and pushes the updated YAML (triggers ArgoCD)

**Required GitHub Repository Secret:**

| Secret Name | Value |
|-------------|-------|
| `AZURE_STORAGE_CONNECTION_STRING` | Full connection string from Azure SAS token generation |

Add it via: **GitHub Repo → Settings → Secrets and variables → Actions → New repository secret**

> **Note:** The pipeline uses `--overwrite` when uploading, so re-runs will always replace the existing blob.

### 3. Kubernetes with KIND (Local Cluster)

```bash
# Create a local KIND cluster
kind create cluster --name churn-model
```

### 4. KServe Setup

```bash
# Install KServe (includes cert-manager, Istio, etc.)
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml

# Wait for KServe controller to be ready
kubectl wait --for=condition=ready pod -l control-plane=kserve-controller-manager -n kserve --timeout=120s
```

### 5. Deploy the Inference Service

**Important:** Before applying, ensure `k8s/inference.yaml` has the correct `storageUri` with a valid SAS token embedded in the URL. The format is:
```
https://storageaccountmlopspoc.blob.core.windows.net/models-container/models/?<SAS_QUERY_STRING>
```

Also ensure `k8s/serviceaccount.yaml` has your valid `AZURE_STORAGE_CONNECTION_STRING` set in the secret (used by GitHub Actions).

```bash
# Apply namespace, secret, and service account
kubectl apply -f k8s/serviceaccount.yaml

# Deploy the KServe inference service
kubectl apply -f k8s/inference.yaml

# Watch until READY = True (may take 2-3 minutes)
kubectl get inferenceservice churn-predictor -n churn-model -w

# Check pods
kubectl get pods -n churn-model

# If stuck in Init:CrashLoopBackOff, check the storage-initializer logs
kubectl logs -l serving.kserve.io/inferenceservice=churn-predictor -n churn-model -c storage-initializer
```

> **KServe Azure Authentication Note:** KServe does not natively support `AZURE_STORAGE_CONNECTION_STRING` from a Kubernetes ServiceAccount secret for private blob access. Instead, the SAS token **must be embedded directly in the `storageUri` HTTPS URL** (as implemented in `inference.yaml`). This is the officially supported approach for SAS-based authentication.

> **SAS Token Expiry:** Regenerate your SAS token before it expires and update both `k8s/inference.yaml` (the `storageUri`) and the GitHub Secret `AZURE_STORAGE_CONNECTION_STRING`.

### 6. Test KServe Inference

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

## Complete MLOps Workflow

```
Developer pushes code to GitHub (main branch)
        │
        ▼
GitHub Actions Pipeline
  ├── Generate dataset
  ├── Train model (churn_model.pkl)
  ├── Upload model → Azure Blob Storage (models-container/models/)
  ├── Update k8s/inference.yaml storageUri
  └── Commit & push updated YAML
        │
        ▼
ArgoCD detects change in k8s/inference.yaml
        │
        ▼
ArgoCD syncs → applies to Kubernetes
        │
        ▼
KServe downloads model from Azure Blob (via SAS URL)
        │
        ▼
KServe serves predictions via REST API
```

---

## Local API Usage (FastAPI)

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

## Key Components

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

- The `storageUri` in `k8s/inference.yaml` contains an embedded SAS token. Regenerate and update it before expiry.
- `k8s/serviceaccount.yaml` contains the Azure connection string secret for GitHub Actions — update this when regenerating the SAS token.
- This is a demo project — production setups require monitoring, logging, secret rotation, and security hardening.
