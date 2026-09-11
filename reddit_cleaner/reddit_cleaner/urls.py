from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="index", permanent=False)),
    path("delete/", include("delete_posts.urls")),
]
