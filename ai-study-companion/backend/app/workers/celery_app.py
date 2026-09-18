"""Celery application configuration."""
import ssl
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ai_study_companion",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
   broker_use_ssl={
    "ssl_cert_reqs": ssl.CERT_REQUIRED,
},
redis_backend_use_ssl={
    "ssl_cert_reqs": ssl.CERT_REQUIRED,
},
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # Only ack after task completes (safer retry)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, # Process one task at a time per worker
    task_max_retries=3,
    task_default_retry_delay=60,  # 60 seconds between retries
)
