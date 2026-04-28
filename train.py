import yaml
import json
import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score

with open('params.yaml', 'r') as f:
    params = yaml.safe_load(f)

# Load data into df
df = pd.read_csv('data/churn_data.csv')

# Features and target
features = ['age', 'tenure_months', 'monthly_charges', 'total_charges', 'num_support_calls']
X = df[features]
y = df['churn']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=params['train']['test_size'], random_state=params['train']['random_state'])

# Train
model = RandomForestClassifier(n_estimators=params['train']['n_estimators'], random_state=params['train']['random_state'])
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

accuracy = accuracy_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_proba)

print(f"Accuracy: {accuracy:.4f}")
print(f"AUC-ROC: {auc:.4f}")

# Save model
with open('models/churn_model.pkl', 'wb') as f:
    pickle.dump(model, f)

print("Model saved to models/churn_model.pkl")

# Save metrics
metrics = {"accuracy": accuracy, "auc_roc": auc}
with open('metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print("Metrics saved to metrics.json")

# MLflow Tracking
import os
import mlflow
import mlflow.sklearn

try:
    # Use K8s MLflow server if available; fallback to local mlruns/
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("churn-predictor")

    with mlflow.start_run():
        # Log all params
        mlflow.log_params({
            "n_samples": params['data']['n_samples'],
            "random_seed": params['data']['random_seed'],
            "n_estimators": params['train']['n_estimators'],
            "test_size": params['train']['test_size'],
            "random_state": params['train']['random_state']
        })
        
        # Log metrics
        mlflow.log_metrics({
            "accuracy": accuracy,
            "auc_roc": auc
        })
        
        # Log model
        mlflow.sklearn.log_model(model, "model")
        print(f"MLflow tracking successful. Logged to {tracking_uri}")
except Exception as e:
    print(f"⚠️ MLflow tracking skipped or failed: {str(e)}")

# Triggered: Thu Mar 27 11:00:52 AM IST 2026
