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

from .config import load_config
from .runner import Runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("ANOMALY_CONFIG_PATH", "config/config.yaml")

config = load_config(CONFIG_PATH)
runner = Runner(config)
scheduler = BackgroundScheduler()


def scheduled_job():
    logger.info("Running scheduled anomaly check pass...")
    results = runner.run_once()
    anomalies = [r for r in results if r.get("is_anomaly")]
    logger.info("Pass complete: %d series checked, %d anomalies", len(results), len(anomalies))


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        scheduled_job,
        "interval",
        seconds=config.scheduler.interval_seconds,
        id="anomaly_check_loop",
        next_run_time=None,  # don't fire instantly; let /check or first interval trigger it
    )
    scheduler.start()
    logger.info(
        "Scheduler started, interval=%ss, %d checks configured",
        config.scheduler.interval_seconds,
        len(config.checks),
    )
    yield
    scheduler.shutdown()


app = FastAPI(title="Prometheus Anomaly Detector", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/status")
def status():
    return {
        "checks_configured": [c.name for c in config.checks],
        "interval_seconds": config.scheduler.interval_seconds,
        "last_run_results": runner.last_run_results,
    }


@app.post("/check")
def trigger_check():
    """Manually trigger a check pass immediately (useful for testing)."""
    results = runner.run_once()
    anomalies = [r for r in results if r.get("is_anomaly")]
    return {"checked": len(results), "anomalies": len(anomalies), "results": results}
