#!/usr/bin/env python3
"""
ChurnShield UI Proxy Server
Serves the UI and proxies requests to KServe to bypass CORS.
Run: python3 server.py
Then open: http://localhost:5000
"""

import json
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

KSERVE_ENDPOINT = "http://churn-predictor-churn-model.mlops-demo.labs.csi-infra.com:10000/v1/models/churn-predictor:predict"


class ProxyHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Custom clean log format."""
        print(f"  [{self.address_string()}] {format % args}")

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/predict":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                req = urllib.request.Request(
                    KSERVE_ENDPOINT,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    result = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._set_cors()
                    self.end_headers()
                    self.wfile.write(result)

            except urllib.error.URLError as e:
                error_msg = str(e.reason) if hasattr(e, "reason") else str(e)
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"KServe unreachable: {error_msg}"}).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Serve static files (the UI)."""
        super().do_GET()


if __name__ == "__main__":
    PORT = 5000
    server = HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    print(f"""
  ╔══════════════════════════════════════════════╗
  ║       ChurnShield AI — Proxy Server          ║
  ╠══════════════════════════════════════════════╣
  ║  UI:      http://localhost:{PORT}              ║
  ║  Proxy:   /predict → KServe                  ║
  ║  Press Ctrl+C to stop                        ║
  ╚══════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
