from django.contrib import admin, messages

from .models import Reminder, TelegramUser


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "first_name",
        "timezone",
        "is_premium",
        "is_blocked",
        "created_at",
    )
    list_filter = ("is_premium", "is_blocked", "timezone")
    search_fields = ("telegram_id", "username", "first_name", "last_name")
    list_editable = ("is_premium", "is_blocked")
    readonly_fields = ("telegram_id", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("telegram_id", "username", "first_name", "last_name", "timezone")}),
        ("Статус", {"fields": ("is_premium", "is_blocked")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )
    actions = ("block_users", "unblock_users", "grant_premium", "revoke_premium")

    @admin.action(description="🔒 Заблокировать")
    def block_users(self, request, queryset):
        n = queryset.update(is_blocked=True)
        self.message_user(request, f"Заблокировано пользователей: {n}", messages.SUCCESS)

    @admin.action(description="🔓 Разблокировать")
    def unblock_users(self, request, queryset):
        n = queryset.update(is_blocked=False)
        self.message_user(request, f"Разблокировано пользователей: {n}", messages.SUCCESS)

    @admin.action(description="⭐ Выдать премиум")
    def grant_premium(self, request, queryset):
        n = queryset.update(is_premium=True)
        self.message_user(request, f"Премиум выдан: {n}", messages.SUCCESS)

    @admin.action(description="⭐ Отозвать премиум")
    def revoke_premium(self, request, queryset):
        n = queryset.update(is_premium=False)
        self.message_user(request, f"Премиум отозван: {n}", messages.SUCCESS)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "user",
        "kind",
        "remind_at",
        "time",
        "weekday",
        "day_of_month",
        "is_active",
        "created_at",
    )
    list_filter = ("kind", "is_active")
    search_fields = ("text", "user__username", "user__telegram_id")
    raw_id_fields = ("user",)
    autocomplete_fields = ("user",)
