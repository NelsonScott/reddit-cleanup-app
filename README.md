# Reddit Cleaner

https://reddit.scottnelson.xyz/

Deletes every post and comment on your Reddit account through the official API.
Sign in with Reddit (OAuth), run a **dry run** to see the counts, then delete for real
while a progress page updates live. Optionally keep recent items, skip subreddits, and
overwrite text before deletion so re-crawled archives get a placeholder.

Inspired by [JosemyDuarte's reddit-cleaner](https://github.com/JosemyDuarte/reddit-cleaner).

## What changed in 2.0 (security + UX)

- **No more typing your Reddit password into a website.** Users authorise via Reddit OAuth;
  the site holds a token in a server-side session (2 h max) and revokes it on sign-out.
  The old "bring your own script app" form still exists but is off unless
  `REDDIT_CLEANER_ALLOW_PASSWORD=1`, and it never logs or stores what you type.
- **Production settings from the environment**: no hard-coded `SECRET_KEY`, `DEBUG` off by
  default, secure/HttpOnly cookies, HSTS, CSP, `X-Frame-Options: DENY`, no admin site,
  no CDN assets (everything served locally via WhiteNoise). `manage.py check --deploy` is clean.
- **Deletion runs in the background** with a live progress page and a Stop button, instead of
  one request that times out on big accounts. Progress lives in sqlite; credentials never do.
- **Dry run first**, a confirmation checkbox for the real thing, per-IP rate limiting,
  overlapping `new`/`top`/`controversial` listings to reach more of Reddit's 1,000-item cap,
  per-item error handling (one failed delete no longer aborts the run).
- **Demo mode** (`REDDIT_CLEANER_FAKE=1`): a fake in-memory account so you can click through
  the whole flow with no network and no real deletions. Used by the test-suite and for QA.
- A small, dependency-free UI with light/dark mode.

## Run locally (demo mode, nothing real is touched)

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt   # or python -m venv + pip
cd reddit_cleaner
REDDIT_CLEANER_DEBUG=1 REDDIT_CLEANER_FAKE=1 ../.venv/bin/python manage.py migrate
REDDIT_CLEANER_DEBUG=1 REDDIT_CLEANER_FAKE=1 ../.venv/bin/python manage.py runserver 127.0.0.1:8000
# open http://127.0.0.1:8000/delete/  → "Sign in with Reddit" bounces straight back as u/demo_user
```

Tests: `REDDIT_CLEANER_DEBUG=1 ../.venv/bin/python manage.py test` (22 tests, ~1 s).

## Run for real

1. Create a Reddit **web app** at https://www.reddit.com/prefs/apps with redirect URI
   `https://<your host>/delete/callback/`.
2. `cp deploy/reddit-cleaner.env.example /etc/reddit-cleaner.env` and fill it in
   (secret key: `python -c 'import secrets; print(secrets.token_urlsafe(50))'`).
3. `deploy/reddit-cleaner.service` (systemd, hardened, runs migrate + collectstatic on start)
   and `deploy/nginx.conf` (TLS + rate limit → gunicorn on 127.0.0.1:8477).
4. Keep gunicorn at **one worker** (see `gunicorn.conf.py`): the job thread and the status
   page must share a process. Threads provide concurrency.

Environment variables are documented at the top of `reddit_cleaner/reddit_cleaner/settings.py`.

## Limits

- Reddit's listings return at most ~1,000 items each; the app unions three listings per type,
  but very old, very active accounts may need a second pass (the dry run will show 0 when clean).
- Reddit rate-limits writes to roughly 60/min, so large accounts take a while. You can close
  the tab; the job keeps running.
- Private messages and saved items are out of scope; delete those from Reddit's own UI.
- One gunicorn process: a restart mid-run stops the job (the page will say `running` forever;
  start a new run — nothing is lost, it just resumes from whatever is still there).
