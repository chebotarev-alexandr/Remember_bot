from django.contrib import admin
from django.urls import include, path

from core.api import my_events

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/my-events/", my_events, name="my_events"),
    path("", include("calendar_sync.urls")),
]
