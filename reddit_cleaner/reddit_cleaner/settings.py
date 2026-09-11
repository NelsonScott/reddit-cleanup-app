"""
Django settings for reddit_cleaner.

Everything deployment-specific comes from environment variables so the repo
contains no secrets and can run with DEBUG off by default.

    REDDIT_CLEANER_SECRET_KEY   required when DEBUG is off
    REDDIT_CLEANER_DEBUG        "1" to enable debug (default off)
    REDDIT_CLEANER_HOSTS        comma-separated ALLOWED_HOSTS
    REDDIT_CLEANER_DB           sqlite path (default: <repo>/data/db.sqlite3)
    REDDIT_OAUTH_CLIENT_ID      the site owner's Reddit "web app" credentials;
    REDDIT_OAUTH_CLIENT_SECRET  when set, users sign in with Reddit OAuth and
    REDDIT_OAUTH_REDIRECT_URI   never type a password into this site
    REDDIT_USER_AGENT           e.g. "web:reddit-cleaner:2.0 (by /u/yourname)"
    REDDIT_CLEANER_ALLOW_PASSWORD  "1" to also offer the legacy script-app form
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("REDDIT_CLEANER_DEBUG", False)

SECRET_KEY = os.environ.get("REDDIT_CLEANER_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise RuntimeError(
            "REDDIT_CLEANER_SECRET_KEY must be set when REDDIT_CLEANER_DEBUG is off "
            "(generate one: python -c 'import secrets; print(secrets.token_urlsafe(50))')"
        )

_hosts = os.environ.get("REDDIT_CLEANER_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()] or (
    ["127.0.0.1", "localhost"] if DEBUG else []
)
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in {"127.0.0.1", "localhost"} and not h.startswith(".")
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "delete_posts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "delete_posts.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "reddit_cleaner.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "reddit_cleaner.wsgi.application"

DATA_DIR = Path(os.environ.get("REDDIT_CLEANER_DATA_DIR", BASE_DIR.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("REDDIT_CLEANER_DB", DATA_DIR / "db.sqlite3"),
        # The deletion job runs in a background thread and writes progress while
        # the request thread reads it: WAL + a busy timeout keep sqlite happy.
        "OPTIONS": {"timeout": 20, "init_command": "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=20000;"},
        # In-memory shared-cache test DBs give instant "table is locked" errors
        # across threads, so tests use a real file too.
        "TEST": {"NAME": DATA_DIR / "test_db.sqlite3"},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "static"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}
    if not DEBUG
    else {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sessions: server-side, short-lived. The Reddit refresh token lives here
# and nowhere else; the browser only ever holds an opaque session id.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 2  # 2 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# --- Transport security (behind nginx/Cloudflare doing TLS)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("REDDIT_CLEANER_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
# W005/W021: HSTS subdomains + preload are deliberately off (this runs on one
# subdomain of a domain that also serves other things).
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; form-action 'self' https://www.reddit.com; "
    "frame-ancestors 'none'; base-uri 'self'"
)

# --- Reddit
# Demo mode: no network, a fake account with a few dozen items. For QA only.
REDDIT_FAKE = env_bool("REDDIT_CLEANER_FAKE", False)
REDDIT_FAKE_DELAY = float(os.environ.get("REDDIT_CLEANER_FAKE_DELAY", "0.15"))
REDDIT_OAUTH_CLIENT_ID = os.environ.get("REDDIT_OAUTH_CLIENT_ID", "")
REDDIT_OAUTH_CLIENT_SECRET = os.environ.get("REDDIT_OAUTH_CLIENT_SECRET", "")
REDDIT_OAUTH_REDIRECT_URI = os.environ.get("REDDIT_OAUTH_REDIRECT_URI", "")
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "web:reddit-cleaner:2.0 (by /u/unknown)")
REDDIT_OAUTH_ENABLED = REDDIT_FAKE or bool(
    REDDIT_OAUTH_CLIENT_ID and REDDIT_OAUTH_CLIENT_SECRET and REDDIT_OAUTH_REDIRECT_URI
)
if REDDIT_FAKE and not REDDIT_OAUTH_REDIRECT_URI:
    REDDIT_OAUTH_REDIRECT_URI = "http://127.0.0.1:8000/delete/callback/"
# Legacy "type your password" path. Off by default when OAuth is configured.
REDDIT_ALLOW_PASSWORD_LOGIN = env_bool("REDDIT_CLEANER_ALLOW_PASSWORD", not REDDIT_OAUTH_ENABLED)
# Overwrite text before deleting (so cached/archived copies show gibberish, not the original)
REDDIT_OVERWRITE_TEXT = os.environ.get("REDDIT_CLEANER_OVERWRITE_TEXT", "[removed by reddit-cleaner]")
# Per-IP throttle for expensive endpoints (start/preview): N requests per window
RATE_LIMIT_MAX = int(os.environ.get("REDDIT_CLEANER_RATE_MAX", "6"))
RATE_LIMIT_WINDOW = int(os.environ.get("REDDIT_CLEANER_RATE_WINDOW", "600"))
JOB_RETENTION_HOURS = int(os.environ.get("REDDIT_CLEANER_JOB_RETENTION_HOURS", "24"))

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"level": "WARNING"},
        "delete_posts": {"level": os.environ.get("REDDIT_CLEANER_LOG_LEVEL", "INFO")},
    },
}
