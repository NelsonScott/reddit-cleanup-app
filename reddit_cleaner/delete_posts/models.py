import uuid

from django.db import models


class CleanupJob(models.Model):
    """Progress record for one deletion run. Never stores credentials."""

    PENDING, RUNNING, DONE, FAILED, CANCELLED = "pending", "running", "done", "failed", "cancelled"
    STATUS_CHOICES = [(s, s) for s in (PENDING, RUNNING, DONE, FAILED, CANCELLED)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    dry_run = models.BooleanField(default=False)
    # Only a display name so the status page can say "for u/x"; no tokens.
    reddit_username = models.CharField(max_length=64, blank=True)
    options = models.JSONField(default=dict)

    submissions_seen = models.IntegerField(default=0)
    submissions_deleted = models.IntegerField(default=0)
    comments_seen = models.IntegerField(default=0)
    comments_deleted = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    current = models.CharField(max_length=200, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    cancel_requested = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def as_dict(self):
        return {
            "id": str(self.id),
            "status": self.status,
            "dry_run": self.dry_run,
            "username": self.reddit_username,
            "submissions_seen": self.submissions_seen,
            "submissions_deleted": self.submissions_deleted,
            "comments_seen": self.comments_seen,
            "comments_deleted": self.comments_deleted,
            "skipped": self.skipped,
            "errors": self.errors,
            "current": self.current,
            "error_message": self.error_message,
            "finished": self.status in {self.DONE, self.FAILED, self.CANCELLED},
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
