from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PrometheusConfig(BaseModel):
    url: str
    token: str | None = None
    timeout_seconds: float = 15.0


class SchedulerConfig(BaseModel):
    interval_seconds: int = Field(300, ge=10)


class WebhookConfig(BaseModel):
    url: str
    format: str = "mattermost"  # "mattermost" | "generic"
    timeout_seconds: float = 10.0
    renotify_after_seconds: int = 1800


class CheckConfig(BaseModel):
    name: str
    query: str
    detector: str
    params: dict = Field(default_factory=dict)

    # Used by non-seasonal detectors: how far back / at what resolution to
    # pull the baseline window.
    history_window: str | None = "2h"
    step: str = "1m"

    # Used only by the seasonal detector: which offsets to compare against
    # and how wide a window to average around each offset point.
    seasonal_offsets: list[str] | None = None
    seasonal_window: str | None = "30m"


class AppConfig(BaseModel):
    name: str = "default"
    prometheus: PrometheusConfig
    scheduler: SchedulerConfig
    webhook: WebhookConfig
    checks: list[CheckConfig]


def load_config(path: str | Path) -> AppConfig:
    """Load a single-tenant config (legacy / backward-compatible)."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    return AppConfig.model_validate(raw)


def load_tenants(path: str | Path) -> list[AppConfig]:
    """Load config supporting both single-tenant and multi-tenant formats.

    Multi-tenant format uses a top-level ``tenants`` list; each entry is an
    AppConfig dict plus an optional ``name`` field.  Single-tenant format
    (legacy) is auto-wrapped into a one-element list.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    if "tenants" in raw:
        return [AppConfig.model_validate(t) for t in raw["tenants"]]
    # Legacy single-tenant file — wrap transparently.
    return [AppConfig.model_validate(raw)]
