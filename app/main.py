"""
Entry point. Runs a FastAPI app for health/status/manual-trigger, plus an
internal APScheduler loop that runs all checks every `interval_seconds` and
fires webhooks on anomalies — no external scheduler or polling required.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from .config import load_tenants
from .runner import Runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("ANOMALY_CONFIG_PATH", "config/config.yaml")

tenants = load_tenants(CONFIG_PATH)
runners: dict[str, Runner] = {t.name: Runner(t) for t in tenants}
scheduler = BackgroundScheduler()


def make_job(name: str, runner: Runner):
    def job():
        logger.info("[%s] Running scheduled anomaly check pass...", name)
        results = runner.run_once()
        anomalies = [r for r in results if r.get("is_anomaly")]
        logger.info("[%s] Pass complete: %d series checked, %d anomalies", name, len(results), len(anomalies))
    return job


@asynccontextmanager
async def lifespan(app: FastAPI):
    for tenant in tenants:
        scheduler.add_job(
            make_job(tenant.name, runners[tenant.name]),
            "interval",
            seconds=tenant.scheduler.interval_seconds,
            id=f"anomaly_check_{tenant.name}",
            next_run_time=None,
        )
        logger.info(
            "Tenant '%s': interval=%ss, prometheus=%s, %d checks",
            tenant.name,
            tenant.scheduler.interval_seconds,
            tenant.prometheus.url,
            len(tenant.checks),
        )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Prometheus Anomaly Detector", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/status")
def status():
    return {
        name: {
            "prometheus": runners[name].config.prometheus.url,
            "checks_configured": [c.name for c in runners[name].config.checks],
            "interval_seconds": runners[name].config.scheduler.interval_seconds,
            "last_run_results": runners[name].last_run_results,
        }
        for name in runners
    }


@app.get("/status/{tenant}")
def tenant_status(tenant: str):
    from fastapi import HTTPException
    runner = runners.get(tenant)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant}' not found")
    return {
        "prometheus": runner.config.prometheus.url,
        "checks_configured": [c.name for c in runner.config.checks],
        "interval_seconds": runner.config.scheduler.interval_seconds,
        "last_run_results": runner.last_run_results,
    }


@app.post("/check")
def trigger_all():
    """Trigger a check pass for all tenants immediately."""
    out = {}
    for name, runner in runners.items():
        results = runner.run_once()
        anomalies = [r for r in results if r.get("is_anomaly")]
        out[name] = {"checked": len(results), "anomalies": len(anomalies)}
    return out


@app.post("/check/{tenant}")
def trigger_tenant(tenant: str):
    """Trigger a check pass for a single tenant immediately."""
    from fastapi import HTTPException
    runner = runners.get(tenant)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant}' not found")
    results = runner.run_once()
    anomalies = [r for r in results if r.get("is_anomaly")]
    return {"checked": len(results), "anomalies": len(anomalies), "results": results}
