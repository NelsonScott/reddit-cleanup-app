import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import reddit_ops
from .forms import CleanupOptionsForm, ScriptAppCredentialsForm
from .models import CleanupJob

logger = logging.getLogger(__name__)

SESSION_TOKEN = "reddit_refresh_token"
SESSION_USER = "reddit_username"
SESSION_STATE = "oauth_state"
SESSION_JOBS = "job_ids"


# ---------------------------------------------------------------- helpers
def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "?"))


def _throttled(request, bucket: str) -> bool:
    key = f"rl:{bucket}:{_client_ip(request)}"
    n = cache.get(key, 0)
    if n >= settings.RATE_LIMIT_MAX:
        return True
    cache.set(key, n + 1, settings.RATE_LIMIT_WINDOW)
    return False


def _remember_job(request, job):
    ids = request.session.get(SESSION_JOBS, [])
    ids.append(str(job.id))
    request.session[SESSION_JOBS] = ids[-10:]


def _owns_job(request, job) -> bool:
    return str(job.id) in request.session.get(SESSION_JOBS, [])


def _purge_old_jobs():
    cutoff = timezone.now() - timezone.timedelta(hours=settings.JOB_RETENTION_HOURS)
    CleanupJob.objects.filter(created_at__lt=cutoff).delete()


def _base_ctx(request):
    return {
        "oauth_enabled": settings.REDDIT_OAUTH_ENABLED,
        "password_enabled": settings.REDDIT_ALLOW_PASSWORD_LOGIN,
        "logged_in_as": request.session.get(SESSION_USER),
    }


# ---------------------------------------------------------------- pages
@require_GET
def index(request):
    ctx = _base_ctx(request)
    ctx["form"] = CleanupOptionsForm()
    return render(request, "delete_posts/index.html", ctx)


@require_GET
def oauth_start(request):
    if not settings.REDDIT_OAUTH_ENABLED:
        raise Http404
    state = secrets.token_urlsafe(24)
    request.session[SESSION_STATE] = state
    url = reddit_ops.authorization_url(reddit_ops.oauth_client(), state)
    return redirect(url)


@require_GET
def oauth_callback(request):
    if not settings.REDDIT_OAUTH_ENABLED:
        raise Http404
    expected = request.session.pop(SESSION_STATE, None)
    state = request.GET.get("state")
    if not expected or not state or not secrets.compare_digest(expected, state):
        messages.error(request, "Login failed: state mismatch. Please try again.")
        return redirect("index")
    if request.GET.get("error"):
        messages.error(request, f"Reddit said: {request.GET['error']}")
        return redirect("index")
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("missing code")
    try:
        reddit = reddit_ops.oauth_client()
        refresh_token = reddit.auth.authorize(code)
        me = reddit.user.me()
    except Exception as e:
        logger.warning("oauth authorize failed: %s", type(e).__name__)
        messages.error(request, "Reddit login failed. Please try again.")
        return redirect("index")
    request.session.cycle_key()
    request.session[SESSION_TOKEN] = refresh_token
    request.session[SESSION_USER] = me.name
    return redirect("index")


@require_POST
def logout(request):
    token = request.session.get(SESSION_TOKEN)
    request.session.flush()
    if token and settings.REDDIT_OAUTH_ENABLED:
        try:
            reddit_ops.revoke(reddit_ops.client_from_refresh_token(token))
        except Exception:
            pass
    messages.info(request, "Signed out; the Reddit token was revoked.")
    return redirect("index")


def _session_client(request):
    token = request.session.get(SESSION_TOKEN)
    if not token or not settings.REDDIT_OAUTH_ENABLED:
        return None
    return reddit_ops.client_from_refresh_token(token)


@require_POST
def preview_view(request):
    """Dry-run counts for the logged-in (OAuth) user."""
    reddit = _session_client(request)
    if reddit is None:
        messages.error(request, "Sign in with Reddit first.")
        return redirect("index")
    form = CleanupOptionsForm(request.POST)
    ctx = _base_ctx(request)
    ctx["form"] = form
    if not form.is_valid():
        return render(request, "delete_posts/index.html", ctx)
    if _throttled(request, "preview"):
        messages.error(request, "Too many requests; wait a few minutes.")
        return render(request, "delete_posts/index.html", ctx)
    try:
        ctx["preview"] = reddit_ops.preview(reddit, form.to_options())
    except Exception as e:
        logger.warning("preview failed: %s", type(e).__name__)
        messages.error(request, "Could not read your Reddit history. Try signing in again.")
    return render(request, "delete_posts/index.html", ctx)


@require_POST
def start(request):
    reddit = _session_client(request)
    if reddit is None:
        messages.error(request, "Sign in with Reddit first.")
        return redirect("index")
    form = CleanupOptionsForm(request.POST)
    ctx = _base_ctx(request)
    ctx["form"] = form
    if not form.is_valid():
        return render(request, "delete_posts/index.html", ctx)
    dry_run = request.POST.get("mode") == "dry_run"
    if not dry_run and not form.cleaned_data.get("confirm"):
        form.add_error("confirm", "Tick the confirmation box to really delete.")
        return render(request, "delete_posts/index.html", ctx)
    if _throttled(request, "start"):
        messages.error(request, "Too many requests; wait a few minutes.")
        return render(request, "delete_posts/index.html", ctx)
    _purge_old_jobs()
    job = CleanupJob.objects.create(
        dry_run=dry_run, options=form.to_options(), reddit_username=request.session.get(SESSION_USER, "")
    )
    _remember_job(request, job)
    logger.info("job %s started (%s) for u/%s", job.id, "dry-run" if dry_run else "delete", job.reddit_username)
    reddit_ops.start_in_background(reddit, job)
    return redirect("job", job_id=job.id)


@require_POST
def legacy(request):
    """Bring-your-own script-app credentials. Off by default when OAuth is set up."""
    if not settings.REDDIT_ALLOW_PASSWORD_LOGIN:
        raise Http404
    form = ScriptAppCredentialsForm(request.POST)
    ctx = _base_ctx(request)
    ctx["legacy_form"] = form
    ctx["form"] = CleanupOptionsForm()
    if not form.is_valid():
        return render(request, "delete_posts/index.html", ctx)
    dry_run = request.POST.get("mode") == "dry_run"
    if not dry_run and not form.cleaned_data.get("confirm"):
        form.add_error("confirm", "Tick the confirmation box to really delete.")
        return render(request, "delete_posts/index.html", ctx)
    if _throttled(request, "start"):
        messages.error(request, "Too many requests; wait a few minutes.")
        return render(request, "delete_posts/index.html", ctx)
    d = form.cleaned_data
    try:
        reddit = reddit_ops.client_from_password(d["reddit_username"], d["password"], d["client_id"], d["client_secret"])
        me = reddit.user.me()  # fail fast on bad credentials, before creating a job
        if me is None:
            raise RuntimeError("not authenticated")
    except Exception as e:
        logger.warning("legacy auth failed: %s", type(e).__name__)
        messages.error(request, "Reddit rejected those credentials. Check the app is a 'script' app and 2FA is off.")
        return render(request, "delete_posts/index.html", ctx)
    _purge_old_jobs()
    job = CleanupJob.objects.create(dry_run=dry_run, options=form.to_options(), reddit_username=me.name)
    _remember_job(request, job)
    logger.info("legacy job %s started (%s) for u/%s", job.id, "dry-run" if dry_run else "delete", me.name)
    reddit_ops.start_in_background(reddit, job)
    return redirect("job", job_id=job.id)


@require_GET
def job_page(request, job_id):
    job = get_object_or_404(CleanupJob, id=job_id)
    if not _owns_job(request, job):
        raise Http404
    ctx = _base_ctx(request)
    ctx["job"] = job
    return render(request, "delete_posts/job.html", ctx)


@require_GET
def job_status(request, job_id):
    job = get_object_or_404(CleanupJob, id=job_id)
    if not _owns_job(request, job):
        raise Http404
    return JsonResponse(job.as_dict())


@require_POST
def job_cancel(request, job_id):
    job = get_object_or_404(CleanupJob, id=job_id)
    if not _owns_job(request, job):
        raise Http404
    if job.status in {CleanupJob.PENDING, CleanupJob.RUNNING}:
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested"])
    return redirect("job", job_id=job.id)


@require_GET
def healthz(request):
    return JsonResponse({"ok": True})
