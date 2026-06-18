"""
Runs all configured checks once: fetch data from Prometheus, run the
appropriate detector for each resulting series, and fire webhooks for new
or still-firing-but-due-for-renotify anomalies.

De-duplication is in-memory only (per the "fully stateless" storage
decision) — restart the service and everything is forgotten, which is fine
for this use case since checks re-run every `interval_seconds` anyway.
"""
from __future__ import annotations

import logging
import time

from .config import AppConfig, CheckConfig
from .detectors import build_detector
from .durations import parse_duration
from .notifiers import send_anomaly_webhook
from .prom_client import PrometheusClient, PrometheusClientError, Series

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = PrometheusClient(
            base_url=config.prometheus.url,
            token=config.prometheus.token,
            timeout=config.prometheus.timeout_seconds,
        )
        # key: (check_name, series_label) -> last time we sent a webhook
        self._last_notified: dict[tuple[str, str], float] = {}
        # last results, kept for the /status endpoint
        self.last_run_results: list[dict] = []

    def run_once(self) -> list[dict]:
        """Run every configured check once. Returns a summary list for inspection."""
        summary = []
        now = time.time()

        for check in self.config.checks:
            try:
                if check.detector == "seasonal":
                    results = self._run_seasonal_check(check, now)
                else:
                    results = self._run_standard_check(check, now)
            except PrometheusClientError as exc:
                logger.error("Check '%s' failed: %s", check.name, exc)
                summary.append({"check": check.name, "error": str(exc)})
                continue

            summary.extend(results)

        self.last_run_results = summary
        return summary

    # -- standard (zscore / robust_mad): pull one recent window, last point is "current" --
    def _run_standard_check(self, check: CheckConfig, now: float) -> list[dict]:
        window_s = parse_duration(check.history_window or "2h")
        series_list = self.client.query_range(
            query=check.query,
            start=now - window_s,
            end=now,
            step=check.step,
        )

        detector = build_detector(check.detector, **check.params)
        out = []
        for series in series_list:
            if len(series.samples) < 2:
                continue
            current = series.samples[-1].value
            history = [s.value for s in series.samples[:-1]]

            result = detector.evaluate(history, current)
            out.append(self._handle_result(check, series, result, now))
        return out

    # -- seasonal: pull one window per offset (1w/2w/3w ago), average each, --
    # -- compare current instant value against that set of seasonal points --
    def _run_seasonal_check(self, check: CheckConfig, now: float) -> list[dict]:
        offsets = check.seasonal_offsets or ["1w", "2w", "3w"]
        window_s = parse_duration(check.seasonal_window or "30m")

        # Current value: average over a short recent window for stability.
        current_series = self.client.query_range(
            query=check.query, start=now - window_s, end=now, step=check.step or "1m"
        )
        current_by_label = {
            s.label_str(): sum(s.values) / len(s.values) for s in current_series if s.values
        }

        # Seasonal points: for each offset, average a window centered on
        # "now - offset".
        seasonal_by_label: dict[str, list[float]] = {label: [] for label in current_by_label}
        for offset in offsets:
            offset_s = parse_duration(offset)
            point_time = now - offset_s
            offset_series = self.client.query_range(
                query=check.query,
                start=point_time - window_s / 2,
                end=point_time + window_s / 2,
                step=check.step or "1m",
            )
            for s in offset_series:
                label = s.label_str()
                if s.values and label in seasonal_by_label:
                    seasonal_by_label[label].append(sum(s.values) / len(s.values))

        detector = build_detector(check.detector, **check.params)
        out = []
        for label, current in current_by_label.items():
            history = seasonal_by_label.get(label, [])
            result = detector.evaluate(history, current)
            # Build a minimal Series stand-in just for label/metric reporting.
            fake_series = Series(metric={"label": label}, samples=[])
            out.append(self._handle_result(check, fake_series, result, now, label_override=label))
        return out

    def _handle_result(self, check, series, result, now, label_override: str | None = None) -> dict:
        label = label_override or series.label_str()
        record = {
            "check": check.name,
            "series": label,
            "detector": result.detector,
            "is_anomaly": result.is_anomaly,
            "actual": result.actual,
            "expected": result.expected,
            "score": result.score,
            "reason": result.reason,
        }

        if result.is_anomaly:
            key = (check.name, label)
            last_sent = self._last_notified.get(key, 0)
            renotify_after = self.config.webhook.renotify_after_seconds
            if now - last_sent >= renotify_after:
                sent = send_anomaly_webhook(
                    webhook_url=self.config.webhook.url,
                    fmt=self.config.webhook.format,
                    check_name=check.name,
                    series_label=label,
                    result=result,
                    timeout=self.config.webhook.timeout_seconds,
                )
                if sent:
                    self._last_notified[key] = now
                record["webhook_sent"] = sent
            else:
                record["webhook_sent"] = False
                record["webhook_skipped_reason"] = "renotify window not elapsed"

        return record
