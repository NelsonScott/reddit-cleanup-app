from django.urls import path
from . import views

urlpatterns = [
    path('', views.delete_reddit_posts, name='delete_reddit_posts')
]