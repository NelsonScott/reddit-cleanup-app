import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DeletePostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "delete_posts"

    def ready(self):
        # Jobs run as threads inside the single gunicorn worker, so a restart
        # kills them. Mark leftovers as failed instead of showing "running" forever.
        from django.db.utils import OperationalError, ProgrammingError

        from .models import CleanupJob

        try:
            n = CleanupJob.objects.filter(status__in=[CleanupJob.PENDING, CleanupJob.RUNNING]).update(
                status=CleanupJob.FAILED, current="", error_message="Server restarted mid-run; start a new run to continue."
            )
            if n:
                logger.warning("marked %d interrupted job(s) as failed at startup", n)
        except (OperationalError, ProgrammingError):
            pass  # tables not created yet (first migrate)
