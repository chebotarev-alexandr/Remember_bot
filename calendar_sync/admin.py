from django.contrib import admin

from .models import CalendarConnection, ReminderEventLink


@admin.register(CalendarConnection)
class CalendarConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "calendar_name", "is_active", "last_synced_at", "created_at")
    list_filter = ("provider", "is_active")
    search_fields = ("user__username", "user__telegram_id", "calendar_name")
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)


@admin.register(ReminderEventLink)
class ReminderEventLinkAdmin(admin.ModelAdmin):
    list_display = ("reminder", "connection", "external_event_id", "updated_at")
    list_filter = ("connection__provider",)
    raw_id_fields = ("reminder", "connection")
