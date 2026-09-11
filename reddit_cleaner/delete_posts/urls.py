from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.oauth_start, name="oauth_start"),
    path("callback/", views.oauth_callback, name="oauth_callback"),
    path("logout/", views.logout, name="logout"),
    path("preview/", views.preview_view, name="preview"),
    path("start/", views.start, name="start"),
    path("legacy/", views.legacy, name="legacy"),
    path("job/<uuid:job_id>/", views.job_page, name="job"),
    path("job/<uuid:job_id>/status/", views.job_status, name="job_status"),
    path("job/<uuid:job_id>/cancel/", views.job_cancel, name="job_cancel"),
    path("healthz/", views.healthz, name="healthz"),
]
