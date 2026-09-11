"""WSGI entry point. Run with: gunicorn -c ../gunicorn.conf.py reddit_cleaner.wsgi:application"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reddit_cleaner.settings")

application = get_wsgi_application()

from delete_posts.startup import recover_interrupted_jobs  # noqa: E402  (apps are ready now)

recover_interrupted_jobs()
