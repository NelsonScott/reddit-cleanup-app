# gunicorn -c gunicorn.conf.py reddit_cleaner.wsgi:application   (run from reddit_cleaner/)
import multiprocessing  # noqa: F401

bind = "127.0.0.1:8477"
# ONE worker: the deletion job runs as a thread inside the worker, and the
# status page must reach the same process. Threads give concurrency instead.
workers = 1
threads = 8
timeout = 120
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
capture_output = True
forwarded_allow_ips = "127.0.0.1"
