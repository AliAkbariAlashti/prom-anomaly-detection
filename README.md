# Prometheus Anomaly Detector

A small, stateless service that periodically queries Prometheus, runs
pluggable statistical anomaly detectors against the results, and fires an
outgoing webhook (Mattermost-compatible, or generic JSON for an automation
layer) whenever something looks abnormal.

Built around the same techniques used in GitLab's and Grafana's PromQL-based
anomaly detection write-ups — no ML runtime, no GPU, no heavy deps. Designed
so ML-based detectors (Prophet-style forecasting, etc.) can be dropped in
later without touching the rest of the system.

## How it works

1. Every `scheduler.interval_seconds`, the service runs all checks defined
   in `config/config.yaml`.
2. For each check, it queries Prometheus for the relevant series, and feeds
   the data into the configured detector.
3. If a series is flagged anomalous, a webhook fires immediately. To avoid
   spamming the same firing anomaly every tick, repeat notifications for the
   same check+series are suppressed until `webhook.renotify_after_seconds`
   has elapsed.
4. No database or persistent state — a restart just means the de-dup memory
   resets, which is fine since every metric gets re-evaluated from scratch
   each tick anyway.

## Detectors

| Detector     | Method                          | Best for                                              |
|--------------|----------------------------------|--------------------------------------------------------|
| `zscore`     | mean / stddev, normal-ish data   | request rates, CPU/memory %, anything fairly Gaussian   |
| `robust_mad` | median / MAD, outlier-resistant  | spiky/bursty metrics, error counts, queue depth          |
| `seasonal`   | median of same time last 1-3 weeks | metrics with strong daily/weekly patterns (traffic, active users) |

Each one returns the same `AnomalyResult` shape (actual, expected, score,
bounds, reason), so adding a new detector — e.g. a Prophet-based forecaster —
just means implementing `BaseDetector.evaluate()` in `app/detectors/` and
registering it in `app/detectors/__init__.py`. The rest of the pipeline
(runner, webhook formatting, config) doesn't change.

## Configuration

Everything is declarative in `config/config.yaml`:

```yaml
checks:
  - name: "high_cpu_usage"
    query: 'avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)'
    detector: "zscore"
    params:
      threshold: 3.0
      min_samples: 10
    history_window: "2h"
    step: "1m"
```

Adding a new metric to watch means adding a new entry here — no code
changes required.

For the `seasonal` detector, use `seasonal_offsets` (e.g. `["1w", "2w",
"3w"]`) and `seasonal_window` instead of `history_window`/`step`; it compares
the current value against the same time-of-week in previous cycles rather
than a flat recent window.

## Running locally

```bash
pip install -r requirements.txt
export ANOMALY_CONFIG_PATH=config/config.yaml
uvicorn app.main:app --reload
```

Endpoints:
- `GET /healthz` — liveness check
- `GET /status` — currently configured checks + results from the last pass
- `POST /check` — trigger a check pass immediately (useful for testing your
  config/webhook without waiting for the scheduler interval)

## Webhook payloads

`webhook.format: mattermost` sends a Slack/Mattermost-compatible
`{"text": "..."}` payload directly to an incoming webhook URL.

`webhook.format: generic` sends the full structured result as JSON, intended
for an automation layer (e.g. n8n) that will route/format it into a richer
Mattermost bot message:

```json
{
  "check_name": "high_cpu_usage",
  "series": "{instance=\"node-1:9100\"}",
  "detector": "zscore",
  "is_anomaly": true,
  "actual": 0.10,
  "expected": 0.95,
  "score": -72.68,
  "lower_bound": 0.91,
  "upper_bound": 0.98,
  "reason": "z-score -72.68 exceeds threshold ±3.0",
  "details": {"mean": 0.95, "stddev": 0.01, "n": 119},
  "timestamp": 1781770466.32
}
```

## Running tests

```bash
pip install pytest
python -m pytest tests/
```

`tests/fake_prom_server.py` is a minimal stand-in Prometheus + webhook
receiver used for manual end-to-end checks; it's not part of the shipped
service.

## Docker

```bash
docker build -t prom-anomaly-detector .
docker run -p 8000:8000 -v $(pwd)/config:/srv/config prom-anomaly-detector
```

## Local MVP test stack

The repo includes a full local scenario for testing the detector without
touching an existing Prometheus:

- `demo-api` exposes synthetic app endpoints and Prometheus metrics.
- `prometheus` scrapes `demo-api`.
- `anomaly-detector` runs this app with `config/local-mvp.yaml`.
- `load-factory` generates baseline traffic, then traffic/error/latency spikes.

Start the core stack:

```bash
docker compose -f docker-compose.mvp.yml up -d --build demo-api prometheus anomaly-detector
```

Start the anomaly load generator:

```bash
docker compose -f docker-compose.mvp.yml --profile load up -d load-factory
```

Useful URLs:

- Detector: http://localhost:8000/status
- Prometheus: http://localhost:9091
- Demo metrics: http://localhost:9102/metrics
- Webhook sink: http://localhost:9102/webhooks

Trigger a detector pass manually:

```bash
curl -X POST http://localhost:8000/check
```

The load scenario starts with a warmup baseline, then injects a traffic spike,
an error spike, and a slow-latency phase. The detector needs a few Prometheus
scrapes before it has enough history, so expect the first anomalies a few
minutes after starting `load-factory`.

## Tuning notes

- `min_samples` guards against false positives from too little history —
  detectors return `is_anomaly: false` with a reason until they have enough
  data.
- Z-score assumes a roughly normal distribution; if a metric is naturally
  spiky (error counts, queue depth), use `robust_mad` instead — it won't get
  thrown off by occasional legitimate spikes already in its training window.
- The seasonal detector's `seasonal_margin_pct` sets a minimum band width as
  a percentage of the predicted value, so very stable seasonal metrics
  (near-zero week-to-week variance) don't get an unrealistically tight band
  that fires on tiny noise.
