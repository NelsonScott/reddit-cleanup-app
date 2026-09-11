import logging

logger = logging.getLogger(__name__)


def recover_interrupted_jobs() -> int:
    """Jobs run as threads inside the single gunicorn worker, so a restart kills
    them. Called once from wsgi.py at worker start (not from AppConfig.ready(),
    which Django warns about) to mark leftovers failed instead of "running" forever."""
    from django.db.utils import OperationalError, ProgrammingError

    from .models import CleanupJob

    try:
        n = CleanupJob.objects.filter(status__in=[CleanupJob.PENDING, CleanupJob.RUNNING]).update(
            status=CleanupJob.FAILED, current="", error_message="Server restarted mid-run; start a new run to continue."
        )
    except (OperationalError, ProgrammingError):  # tables not created yet
        return 0
    if n:
        logger.warning("marked %d interrupted job(s) as failed at startup", n)
    return n
