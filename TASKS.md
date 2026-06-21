# Refactor Tasks

| # | Task | State |
|---|------|-------|
| 1 | Create Django project: run startproject + startapp detector | todo |
| 2 | Update requirements.txt: remove FastAPI/uvicorn/APScheduler, add Django + DRF + psycopg2-binary | todo |
| 3 | Update requirements.txt: add celery, redis, django-celery-beat | todo |
| 4 | Update requirements.txt: add drf-spectacular | todo |
| 5 | Configure DATABASES in settings.py (PostgreSQL, values from env vars) | todo |
| 6 | Configure INSTALLED_APPS in settings.py (rest_framework, drf_spectacular, django_celery_beat, detector) | todo |
| 7 | Configure DRF default settings in settings.py | todo |
| 8 | Configure Celery broker/backend settings in settings.py | todo |
| 9 | Create anomaly_service/celery.py (Celery app instance) + update __init__.py to load it | todo |
| 10 | Define PrometheusInstance model (name, url, auth_type, auth_config, enabled) | todo |
| 11 | Define MattermostChannel model (name, webhook_url, enabled) | todo |
| 12 | Define AlertRoute model (FK to PrometheusInstance + MattermostChannel, unique_together) | todo |
| 13 | Define MetricQuery model (metric_type unique, promql) | todo |
| 14 | Define Threshold model (metric_type, warning_threshold, critical_threshold, auto_update, interval_seconds) | todo |
| 15 | Define AnomalyEvent model (FK prometheus, host, metric_type, value, threshold, severity, labels, detected_at, M2M sent_to_channels) | todo |
| 16 | Create and apply initial migration (makemigrations + migrate) | todo |
| 17 | Create PrometheusRepository (get_all_enabled, get_by_id) | todo |
| 18 | Create MattermostRepository (get_all_enabled, get_by_id) | todo |
| 19 | Create AlertRouteRepository (get_channels_for_instance) | todo |
| 20 | Create MetricQueryRepository (get_all, get_by_metric_type) | todo |
| 21 | Create ThresholdRepository (get_all, get_by_metric_type) | todo |
| 22 | Create AnomalyEventRepository (create, mark_channels_sent) | todo |
| 23 | Create serializer for PrometheusInstance | todo |
| 24 | Create serializer for MattermostChannel | todo |
| 25 | Create serializer for AlertRoute | todo |
| 26 | Create serializer for MetricQuery | todo |
| 27 | Create serializer for Threshold | todo |
| 28 | Create serializer for AnomalyEvent (read-only) | todo |
| 29 | Create PrometheusInstance ViewSet (full CRUD) + register on router | todo |
| 30 | Create MattermostChannel ViewSet (full CRUD) + register on router | todo |
| 31 | Create AlertRoute ViewSet (POST + GET + DELETE) + register on router | todo |
| 32 | Create MetricQuery ViewSet (GET + PUT only) + register on router | todo |
| 33 | Create Threshold ViewSet (GET + PUT only) + register on router | todo |
| 34 | Create AnomalyEvent ViewSet (read-only) + register on router | todo |
| 35 | Wire DefaultRouter into urls.py with /api/ prefix | todo |
| 36 | Add drf-spectacular schema + swagger-ui URLs to urls.py | todo |
| 37 | Create base Detector abstract class with detect() interface | todo |
| 38 | Implement ThresholdDetector (compare value vs warning/critical, return severity or None) | todo |
| 39 | Adapt prom_client.py as a standalone query helper (URL + auth_type + auth_config + PromQL) | todo |
| 40 | Create run_anomaly_checks Celery task: loop instances → queries → ThresholdDetector → persist AnomalyEvent | todo |
| 41 | Create MattermostNotifier: format host/metric/value/threshold/severity message + POST to webhook_url | todo |
| 42 | Wire notifier into task: lookup AlertRoutes per instance, call notifier, update sent_to_channels | todo |
| 43 | Update Dockerfile: switch to gunicorn entrypoint, remove uvicorn | todo |
| 44 | Update docker-compose: add postgres + redis services | todo |
| 45 | Update docker-compose: add web (Django), worker (Celery), beat services | todo |
| 46 | Remove old FastAPI code: app/main.py, app/runner.py, app/config.py, app/durations.py | todo |
| 47 | Remove old app/detectors/ and app/notifiers/ directories | todo |
| 48 | Remove old config YAML files: config/config.yaml, config/local-mvp.yaml | todo |
| 49 | Update README: new setup steps, API endpoints, docker-compose services | todo |
