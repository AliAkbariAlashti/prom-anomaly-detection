"""
Stand-in Prometheus + webhook receiver for manual end-to-end testing.
Not part of the shipped service — just used to sanity check runner.py
against something that looks like real Prometheus API responses.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

received_webhooks = []


def make_matrix_response(metric_label: dict, values: list[float], start: float, step: int):
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": metric_label,
                    "values": [[start + i * step, str(v)] for i, v in enumerate(values)],
                }
            ],
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet

    def do_GET(self):
        if self.path.startswith("/api/v1/query_range"):
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(self.path).query)
            query = qs["query"][0]
            start = float(qs["start"][0])
            end = float(qs["end"][0])
            step = 60

            # Simulate different series depending on the query, with a
            # deliberate spike injected near the end for the "current" point.
            import random

            random.seed(42)
            if "cpu" in query:
                values = [0.95 + random.uniform(-0.02, 0.02) for _ in range(119)] + [0.10]
                metric = {"instance": "node-1:9100"}
            elif "5.." in query:
                values = [2.0 + random.uniform(-0.3, 0.3) for _ in range(119)] + [2.4]
                metric = {"job": "api"}
            else:
                # seasonal query: same shape with noise regardless of offset window
                n_points = max(2, int((end - start) / step))
                values = [100.0 + random.uniform(-5, 5) for _ in range(n_points)]
                metric = {"job": "web"}

            body = json.dumps(make_matrix_response(metric, values, start, step)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        received_webhooks.append(json.loads(body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")


def run(port=9999):
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    run()
