from django.urls import path

from . import views

urlpatterns = [
    path("callback/google/", views.google_callback, name="google_callback"),
    path("callback/yandex/", views.yandex_callback, name="yandex_callback"),
]
