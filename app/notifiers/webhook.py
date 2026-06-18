"""
Sends anomaly notifications to an outgoing webhook.

Two formats:
- "mattermost": posts a {"text": "..."} payload compatible with Mattermost
  incoming webhooks (and Slack-compatible webhooks generally).
- "generic": posts the full structured anomaly payload as JSON, intended
  for an automation layer (n8n, etc.) that will format/route it further,
  e.g. into a Mattermost bot message with richer formatting.
"""
from __future__ import annotations

import logging
import time

import httpx

from ..detectors.base import AnomalyResult

logger = logging.getLogger(__name__)


def _format_mattermost_text(check_name: str, series_label: str, result: AnomalyResult) -> str:
    lines = [
        f"**🚨 Anomaly detected: `{check_name}`**",
        f"Series: `{series_label}`",
        f"Detector: `{result.detector}`",
        f"Actual: `{result.actual:.4g}`"
        + (f"  |  Expected: `{result.expected:.4g}`" if result.expected is not None else ""),
        f"Score: `{result.score:.2f}`",
    ]
    if result.lower_bound is not None and result.upper_bound is not None:
        lines.append(f"Normal range: `[{result.lower_bound:.4g}, {result.upper_bound:.4g}]`")
    if result.reason:
        lines.append(f"_{result.reason}_")
    return "\n".join(lines)


def send_anomaly_webhook(
    webhook_url: str,
    fmt: str,
    check_name: str,
    series_label: str,
    result: AnomalyResult,
    timeout: float = 10.0,
) -> bool:
    """Returns True on success, False on failure (never raises)."""
    try:
        if fmt == "mattermost":
            payload = {"text": _format_mattermost_text(check_name, series_label, result)}
        else:  # "generic"
            payload = {
                "check_name": check_name,
                "series": series_label,
                "detector": result.detector,
                "is_anomaly": result.is_anomaly,
                "actual": result.actual,
                "expected": result.expected,
                "score": result.score,
                "lower_bound": result.lower_bound,
                "upper_bound": result.upper_bound,
                "reason": result.reason,
                "details": result.details,
                "timestamp": time.time(),
            }

        resp = httpx.post(webhook_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.error("Webhook delivery failed for check '%s': %s", check_name, exc)
        return False
    except (ValueError, TypeError) as exc:
        logger.error("Webhook payload for check '%s' was not valid JSON: %s", check_name, exc)
        return False
