from django.contrib import admin
from django.urls import include, path

from core.api import my_events, weather

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/my-events/", my_events, name="my_events"),
    path("api/weather/", weather, name="weather"),
    path("", include("calendar_sync.urls")),
]
