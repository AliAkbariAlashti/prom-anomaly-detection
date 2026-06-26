import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anomaly_service.settings')

app = Celery('anomaly_service')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
