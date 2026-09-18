"""Celery application configuration."""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "asc_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.document_pipeline", "app.workers.learning_workflow"],
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
