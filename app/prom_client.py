"""
Minimal client for the Prometheus HTTP API.

Only what we need: instant query and range query. Kept dependency-free
(just httpx) so it's easy to vendor or swap out.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    timestamp: float
    value: float


@dataclass
class Series:
    metric: dict
    samples: list[Sample]

    @property
    def values(self) -> list[float]:
        return [s.value for s in self.samples]

    def label_str(self) -> str:
        """Human readable label set, e.g. {job="api", instance="10.0.0.1:9090"}"""
        if not self.metric:
            return "{}"
        pairs = ", ".join(f'{k}="{v}"' for k, v in sorted(self.metric.items()))
        return "{" + pairs + "}"


class PrometheusClientError(RuntimeError):
    pass


class PrometheusClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def query_range(
        self,
        query: str,
        start: float,
        end: float,
        step: str = "60s",
    ) -> list[Series]:
        """Run a range query and return one Series per resulting time series."""
        url = f"{self.base_url}/api/v1/query_range"
        params = {"query": query, "start": start, "end": end, "step": step}
        try:
            resp = httpx.get(url, params=params, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrometheusClientError(f"query_range failed for '{query}': {exc}") from exc

        payload = resp.json()
        if payload.get("status") != "success":
            raise PrometheusClientError(f"Prometheus returned error: {payload}")

        result_type = payload["data"]["result_type" if "result_type" in payload["data"] else "resultType"]
        if result_type != "matrix":
            raise PrometheusClientError(
                f"Expected matrix result for range query, got '{result_type}'"
            )

        series_list = []
        for result in payload["data"]["result"]:
            samples = [Sample(timestamp=ts, value=float(val)) for ts, val in result["values"]]
            series_list.append(Series(metric=result["metric"], samples=samples))
        return series_list

    def query_instant(self, query: str, time_: float | None = None) -> list[Series]:
        """Run an instant query, returned as single-sample Series for consistency."""
        url = f"{self.base_url}/api/v1/query"
        params = {"query": query}
        if time_ is not None:
            params["time"] = time_
        try:
            resp = httpx.get(url, params=params, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrometheusClientError(f"query failed for '{query}': {exc}") from exc

        payload = resp.json()
        if payload.get("status") != "success":
            raise PrometheusClientError(f"Prometheus returned error: {payload}")

        now = time_ or time.time()
        series_list = []
        for result in payload["data"]["result"]:
            ts, val = result["value"]
            series_list.append(
                Series(metric=result["metric"], samples=[Sample(timestamp=ts, value=float(val))])
            )
        return series_list
