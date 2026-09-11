"""Reddit-side logic: building clients, previewing, and running a cleanup.

Kept free of Django request objects so it can be unit-tested with fake PRAW
objects and run from a background thread.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import praw
from django.conf import settings
from django.db import close_old_connections

from .models import CleanupJob

logger = logging.getLogger(__name__)

OAUTH_SCOPES = ["identity", "history", "edit", "read"]


# ---------------------------------------------------------------- clients
def _fake():
    """Demo mode (REDDIT_CLEANER_FAKE=1): an in-memory account, no network."""
    from . import fake_reddit

    global _FAKE_ACCOUNT
    if _FAKE_ACCOUNT is None:
        _FAKE_ACCOUNT = fake_reddit.make_account(delay=settings.REDDIT_FAKE_DELAY)
        _FAKE_ACCOUNT.redirect_uri = settings.REDDIT_OAUTH_REDIRECT_URI
    return _FAKE_ACCOUNT


_FAKE_ACCOUNT = None


def oauth_client() -> praw.Reddit:
    """Unauthenticated client using the site's own web-app credentials."""
    if settings.REDDIT_FAKE:
        return _fake()
    return praw.Reddit(
        client_id=settings.REDDIT_OAUTH_CLIENT_ID,
        client_secret=settings.REDDIT_OAUTH_CLIENT_SECRET,
        redirect_uri=settings.REDDIT_OAUTH_REDIRECT_URI,
        user_agent=settings.REDDIT_USER_AGENT,
        check_for_updates=False,
    )


def client_from_refresh_token(refresh_token: str) -> praw.Reddit:
    if settings.REDDIT_FAKE:
        return _fake()
    return praw.Reddit(
        client_id=settings.REDDIT_OAUTH_CLIENT_ID,
        client_secret=settings.REDDIT_OAUTH_CLIENT_SECRET,
        refresh_token=refresh_token,
        user_agent=settings.REDDIT_USER_AGENT,
        check_for_updates=False,
    )


def client_from_password(username: str, password: str, client_id: str, client_secret: str) -> praw.Reddit:
    if settings.REDDIT_FAKE:
        return _fake()
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=settings.REDDIT_USER_AGENT,
        check_for_updates=False,
    )


def authorization_url(reddit: praw.Reddit, state: str) -> str:
    # duration="temporary" => access token only, no refresh token stored anywhere
    # long-term. We still get ~1h which is plenty for a cleanup run; for very
    # large accounts use "permanent" and revoke afterwards (see revoke()).
    return reddit.auth.url(scopes=OAUTH_SCOPES, state=state, duration="permanent")


def revoke(reddit: praw.Reddit) -> None:
    """Best-effort: drop the refresh token server-side when we're done."""
    try:
        if settings.REDDIT_FAKE:
            reddit.revoked = True
            return
        auth = reddit._core._authorizer  # noqa: SLF001 - PRAW has no public revoke on Reddit
        auth.revoke()
    except Exception:  # pragma: no cover - best effort
        logger.info("token revoke failed (ignored)")


# ---------------------------------------------------------------- filtering
def _cutoff(options: dict) -> float | None:
    keep_days = options.get("keep_days")
    if keep_days is None or keep_days == "":
        return None
    return (datetime.now(timezone.utc) - timedelta(days=int(keep_days))).timestamp()


def should_skip(item, options: dict, cutoff: float | None) -> str | None:
    """Return a reason string if the item must be kept, else None."""
    if cutoff is not None and getattr(item, "created_utc", 0) >= cutoff:
        return "newer than keep window"
    sub = getattr(item, "subreddit", None)
    name = (getattr(sub, "display_name", None) or str(sub or "")).lower()
    if name and name in set(options.get("skip_subreddits") or []):
        return f"in r/{name}"
    return None


def _iter_items(user, options: dict):
    """Yield ("submission"|"comment", item). Uses several listings because
    Reddit caps each at ~1000 items; the union reaches more of an old account."""
    seen = set()
    if options.get("delete_submissions", True):
        for listing in (user.submissions.new, user.submissions.top, user.submissions.controversial):
            for s in listing(limit=None):
                if s.id in seen:
                    continue
                seen.add(s.id)
                yield "submission", s
    if options.get("delete_comments", True):
        for listing in (user.comments.new, user.comments.top, user.comments.controversial):
            for c in listing(limit=None):
                if c.id in seen:
                    continue
                seen.add(c.id)
                yield "comment", c


# ---------------------------------------------------------------- preview
def preview(reddit: praw.Reddit, options: dict, limit_per_listing: int = 1000) -> dict:
    """Count what a run would touch without changing anything."""
    user = reddit.user.me()
    cutoff = _cutoff(options)
    out = {"username": user.name, "submissions": 0, "comments": 0, "skipped": 0, "sample": []}
    for kind, item in _iter_items(user, options):
        if should_skip(item, options, cutoff):
            out["skipped"] += 1
            continue
        out[kind + "s"] += 1
        if len(out["sample"]) < 8:
            out["sample"].append(_describe(kind, item))
    return out


def _describe(kind: str, item) -> str:
    sub = getattr(item, "subreddit", None)
    sub = getattr(sub, "display_name", None) or str(sub or "?")
    if kind == "submission":
        return f"r/{sub}: {getattr(item, 'title', '')[:80]}"
    return f"r/{sub}: {getattr(item, 'body', '')[:80]!r}"


# ---------------------------------------------------------------- run
PROGRESS_FIELDS = [
    "status", "reddit_username", "submissions_seen", "submissions_deleted", "comments_seen",
    "comments_deleted", "skipped", "errors", "current", "error_message", "finished_at", "updated_at",
]


class _Progress:
    """Writes progress at most twice a second. Only progress columns are
    written, so a concurrent cancel request (another column) is never clobbered."""

    def __init__(self, job: CleanupJob):
        self.job = job
        self._last_flush = 0.0

    def flush(self, force=False):
        now = time.monotonic()
        if force or now - self._last_flush > 0.5:
            self.job.save(update_fields=PROGRESS_FIELDS)
            self._last_flush = now

    def cancelled(self) -> bool:
        self.job.refresh_from_db(fields=["cancel_requested"])
        return self.job.cancel_requested


def run_cleanup(reddit: praw.Reddit, job: CleanupJob) -> CleanupJob:
    """Delete everything the options allow, updating `job` as we go."""
    options = job.options or {}
    cutoff = _cutoff(options)
    overwrite = options.get("overwrite_first", True)
    prog = _Progress(job)
    try:
        job.status = CleanupJob.RUNNING
        prog.flush(force=True)
        user = reddit.user.me()
        job.reddit_username = user.name
        for kind, item in _iter_items(user, options):
            if prog.cancelled():
                job.status = CleanupJob.CANCELLED
                break
            if kind == "submission":
                job.submissions_seen += 1
            else:
                job.comments_seen += 1
            reason = should_skip(item, options, cutoff)
            if reason:
                job.skipped += 1
                prog.flush()
                continue
            job.current = _describe(kind, item)[:200]
            if job.dry_run:
                if kind == "submission":
                    job.submissions_deleted += 1
                else:
                    job.comments_deleted += 1
                prog.flush()
                continue
            try:
                if overwrite and _is_editable(kind, item):
                    try:
                        item.edit(settings.REDDIT_OVERWRITE_TEXT)
                    except Exception as e:  # editing is optional; deletion is what matters
                        logger.info("edit failed for %s %s: %s", kind, item.id, type(e).__name__)
                item.delete()
                if kind == "submission":
                    job.submissions_deleted += 1
                else:
                    job.comments_deleted += 1
            except Exception as e:
                job.errors += 1
                logger.warning("delete failed for %s %s: %s", kind, item.id, type(e).__name__)
            prog.flush()
        else:
            job.status = CleanupJob.DONE
    except Exception as e:
        logger.exception("cleanup job %s failed", job.id)
        job.status = CleanupJob.FAILED
        job.error_message = f"{type(e).__name__}: {str(e)[:300]}"
    job.current = ""
    job.finished_at = datetime.now(timezone.utc)
    prog.flush(force=True)
    return job


def _is_editable(kind: str, item) -> bool:
    if kind == "comment":
        return True
    # only self-posts have editable bodies
    return bool(getattr(item, "is_self", False))


def start_in_background(reddit: praw.Reddit, job: CleanupJob, revoke_after: bool = False) -> threading.Thread:
    def _target():
        try:
            run_cleanup(reddit, job)
        finally:
            if revoke_after:
                revoke(reddit)
            close_old_connections()

    t = threading.Thread(target=_target, name=f"cleanup-{job.id}", daemon=True)
    t.start()
    return t
