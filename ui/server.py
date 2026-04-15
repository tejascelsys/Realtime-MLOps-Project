#!/usr/bin/env python3
"""
ChurnShield UI Proxy Server (with Monitoring)
Serves the UI, proxies requests to KServe, exposes Prometheus metrics,
and serves Evidently monitoring reports.

Run: python3 server.py
Then open: http://localhost:5000
Monitoring: http://localhost:5000/monitoring
Metrics: http://localhost:5000/metrics
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ─── Prometheus metrics ───────────────────────────
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("  ⚠️  prometheus_client not installed. /metrics endpoint disabled.")
    print("  Install with: pip install prometheus_client")

if PROMETHEUS_AVAILABLE:
    PREDICTION_REQUESTS = Counter(
        "churnshield_prediction_requests_total",
        "Total prediction requests",
        ["result"],  # churn / no_churn
    )
    PREDICTION_LATENCY = Histogram(
        "churnshield_prediction_latency_seconds",
        "Prediction request latency in seconds",
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    PREDICTION_ERRORS = Counter(
        "churnshield_prediction_errors_total",
        "Total prediction errors",
        ["error_type"],  # kserve_unreachable, server_error
    )
    PREDICTION_PROBABILITY = Histogram(
        "churnshield_prediction_probability",
        "Distribution of churn probabilities",
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    MODEL_INFO = Gauge(
        "churnshield_model_info",
        "Model metadata",
        ["model_type", "features"],
    )
    MODEL_INFO.labels(model_type="RandomForest", features="5").set(1)


KSERVE_ENDPOINT = os.getenv(
    "KSERVE_ENDPOINT",
    "http://churn-predictor-churn-model.mlops-demo.labs.csi-infra.com:10000/v1/models/churn-predictor:predict"
)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DATA_ROOT = Path(os.getenv("DATA_ROOT", str(PROJECT_ROOT)))
MONITORING_DIR = DATA_ROOT / "monitoring"
REPORTS_DIR = MONITORING_DIR / "reports"
METRICS_PATH = DATA_ROOT / "metrics.json"


class ProxyHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Custom clean log format."""
        print(f"  [{self.address_string()}] {format % args}")

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/predict":
            self._handle_predict()
        elif self.path == "/run-monitoring":
            self._handle_run_monitoring()
        elif self.path == "/simulate-drift":
            self._handle_simulate_drift()
        elif self.path == "/reset-drift":
            self._handle_reset_drift()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_metrics_live(self):
        """Serve the live metrics.json from the project root."""
        try:
            if METRICS_PATH.exists():
                with open(METRICS_PATH, "r") as f:
                    data = json.load(f)
                self._send_json(200, data)
            else:
                self._send_json(404, {"error": "metrics.json not found"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_predict(self):
        """Proxy prediction to KServe with Prometheus instrumentation."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        start_time = time.time()
        try:
            req = urllib.request.Request(
                KSERVE_ENDPOINT,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = resp.read()
                duration = time.time() - start_time

                # Track Prometheus metrics
                if PROMETHEUS_AVAILABLE:
                    PREDICTION_LATENCY.observe(duration)
                    try:
                        response_data = json.loads(result)
                        prediction = response_data.get("predictions", [None])[0]
                        if prediction is not None:
                            label = "churn" if prediction == 1 else "no_churn"
                            PREDICTION_REQUESTS.labels(result=label).inc()
                    except (json.JSONDecodeError, IndexError, KeyError):
                        PREDICTION_REQUESTS.labels(result="unknown").inc()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(result)

        except urllib.error.URLError as e:
            if PROMETHEUS_AVAILABLE:
                PREDICTION_ERRORS.labels(error_type="kserve_unreachable").inc()

            error_msg = str(e.reason) if hasattr(e, "reason") else str(e)
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(
                json.dumps({"error": f"KServe unreachable: {error_msg}"}).encode()
            )

        except Exception as e:
            if PROMETHEUS_AVAILABLE:
                PREDICTION_ERRORS.labels(error_type="server_error").inc()

            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _handle_run_monitoring(self):
        """Run monitoring/monitor.py and return status."""
        try:
            monitor_script = str(MONITORING_DIR / "monitor.py")
            python_exec = "/home/tejasdp/Realtime-MLOps-Project/monitoring_venv/bin/python3.11"

            result = subprocess.run(
                [python_exec, monitor_script],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                self._send_json(200, {
                    "status": "ok",
                    "output": result.stdout[-500:] if result.stdout else "",
                })
            else:
                self._send_json(500, {
                    "status": "error",
                    "error": result.stderr[-500:] if result.stderr else "Unknown error",
                })

        except subprocess.TimeoutExpired:
            self._send_json(500, {"status": "error", "error": "Report generation timed out (120s)"})
        except Exception as e:
            self._send_json(500, {"status": "error", "error": str(e)})


    def _handle_simulate_drift(self):
        """Run monitoring/simulate_drift.py and return status."""
        try:
            drift_script = str(MONITORING_DIR / "simulate_drift.py")
            result = subprocess.run(
                [sys.executable, drift_script],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._send_json(200, {"status": "ok", "output": result.stdout[-500:]})
            else:
                self._send_json(500, {"status": "error", "error": result.stderr[-500:]})
        except Exception as e:
            self._send_json(500, {"status": "error", "error": str(e)})

    def _handle_reset_drift(self):
        """Delete drifted data file to reset to baseline."""
        try:
            drifted_path = MONITORING_DIR / "drifted_data.csv"
            if drifted_path.exists():
                os.remove(drifted_path)
            self._send_json(200, {"status": "ok"})
        except Exception as e:
            self._send_json(500, {"status": "error", "error": str(e)})

    def do_GET(self):
        """Serve static files, monitoring page, reports, and Prometheus metrics."""
        path_base = self.path.split('?')[0]
        
        if path_base == "/monitoring" or path_base == "/monitoring/":
            self._serve_file(SCRIPT_DIR / "monitoring.html", "text/html")
        elif path_base == "/metrics":
            self._serve_prometheus_metrics()
        elif path_base == "/metrics-live":
            self._handle_metrics_live()
        elif path_base.startswith("/reports/"):
            # Serve Evidently HTML reports
            filename = path_base.split("/reports/")[1]
            filepath = REPORTS_DIR / filename
            if filepath.exists() and filepath.is_file():
                content_type = "text/html" if filename.endswith(".html") else "application/json"
                self._serve_file(filepath, content_type)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            super().do_GET()

    def _serve_file(self, filepath, content_type):
        """Serve a file with the given content type."""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self._set_cors()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _serve_prometheus_metrics(self):
        """Serve Prometheus metrics endpoint."""
        if not PROMETHEUS_AVAILABLE:
            self._send_json(503, {"error": "prometheus_client not installed"})
            return
        output = generate_latest()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(output)


if __name__ == "__main__":
    PORT = 5000
    server = HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    metrics_status = "✅ Enabled" if PROMETHEUS_AVAILABLE else "❌ Disabled (pip install prometheus_client)"
    print(f"""
  ╔══════════════════════════════════════════════════╗
  ║       ChurnShield AI — Proxy Server              ║
  ╠══════════════════════════════════════════════════╣
  ║  UI:         http://localhost:{PORT}               ║
  ║  Monitoring: http://localhost:{PORT}/monitoring     ║
  ║  Metrics:    http://localhost:{PORT}/metrics         ║
  ║  Proxy:      /predict → KServe                    ║
  ║  Prometheus: {metrics_status:<36s}║
  ║  Press Ctrl+C to stop                            ║
  ╚══════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
