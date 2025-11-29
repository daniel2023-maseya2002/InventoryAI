# backend/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# read config from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# auto-discover tasks in installed apps
app.autodiscover_tasks()
