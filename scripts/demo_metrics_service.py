from __future__ import annotations

import json
import random
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "0.0.0.0"
PORT = 9102

_lock = threading.Lock()
_requests: dict[tuple[str, str], int] = defaultdict(int)
_errors: dict[tuple[str, str], int] = defaultdict(int)
_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
_latency_count: dict[tuple[str, str], int] = defaultdict(int)
_webhooks: deque[dict] = deque(maxlen=50)


def _labels(route: str, status: str) -> str:
    return f'route="{route}",status="{status}"'


def _record(route: str, status: str, latency: float) -> None:
    key = (route, status)
    with _lock:
        _requests[key] += 1
        if status.startswith("5"):
            _errors[key] += 1
        _latency_sum[key] += latency
        _latency_count[key] += 1


def _render_metrics() -> str:
    with _lock:
        lines = [
            "# HELP demo_http_requests_total Total synthetic HTTP requests.",
            "# TYPE demo_http_requests_total counter",
        ]
        for (route, status), value in sorted(_requests.items()):
            lines.append(f"demo_http_requests_total{{{_labels(route, status)}}} {value}")

        lines.extend(
            [
                "# HELP demo_http_errors_total Total synthetic 5xx HTTP responses.",
                "# TYPE demo_http_errors_total counter",
            ]
        )
        for (route, status), value in sorted(_errors.items()):
            lines.append(f"demo_http_errors_total{{{_labels(route, status)}}} {value}")

        lines.extend(
            [
                "# HELP demo_http_request_latency_seconds Synthetic request latency.",
                "# TYPE demo_http_request_latency_seconds summary",
            ]
        )
        for (route, status), value in sorted(_latency_sum.items()):
            labels = _labels(route, status)
            lines.append(f"demo_http_request_latency_seconds_sum{{{labels}}} {value:.6f}")
            lines.append(
                f"demo_http_request_latency_seconds_count{{{labels}}} {_latency_count[(route, status)]}"
            )

        lines.extend(
            [
                "# HELP demo_anomaly_webhooks_total Webhooks received by the demo sink.",
                "# TYPE demo_anomaly_webhooks_total counter",
                f"demo_anomaly_webhooks_total {len(_webhooks)}",
            ]
        )
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "demo-metrics-service/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            self._send(200, _render_metrics(), "text/plain; version=0.0.4")
            return

        if parsed.path == "/webhooks":
            with _lock:
                payload = json.dumps(list(_webhooks), indent=2)
            self._send(200, payload, "application/json")
            return

        if parsed.path in {"/checkout", "/search"}:
            params = parse_qs(parsed.query)
            mode = params.get("mode", ["normal"])[0]
            route = parsed.path

            if mode == "error":
                latency = random.uniform(0.08, 0.35)
                time.sleep(latency)
                _record(route, "500", latency)
                self._send(500, '{"ok": false, "mode": "error"}\n', "application/json")
                return

            if mode == "slow":
                latency = random.uniform(0.8, 1.8)
            else:
                latency = random.uniform(0.025, 0.12)
            time.sleep(latency)
            _record(route, "200", latency)
            self._send(200, '{"ok": true}\n', "application/json")
            return

        self._send(404, "not found\n", "text/plain")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            self._send(404, "not found\n", "text/plain")
            return

        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}

        with _lock:
            _webhooks.appendleft({"received_at": time.time(), "payload": payload})
        self._send(204, "", "text/plain")

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"demo metrics service listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
