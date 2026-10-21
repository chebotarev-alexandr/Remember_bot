"""Модели синхронизации календарей."""

from django.db import models

from core.models import Reminder, TelegramUser


class CalendarConnection(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google Calendar"
        YANDEX = "yandex", "Яндекс Календарь"

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="calendar_connections",
        verbose_name="Пользователь",
    )
    provider = models.CharField("Провайдер", max_length=10, choices=Provider.choices)
    # Google: {"token", "refresh_token", "client_id", "client_secret", "token_uri"}
    # Yandex: {"username", "app_password"}
    credentials = models.JSONField("Учётные данные", default=dict, blank=True)
    calendar_id = models.CharField("ID календаря", max_length=512, blank=True)
    calendar_name = models.CharField("Название календаря", max_length=255, blank=True)
    is_active = models.BooleanField("Активно", default=True)
    last_synced_at = models.DateTimeField("Последняя синхронизация", null=True, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Подключение календаря"
        verbose_name_plural = "Подключения календарей"
        unique_together = (("user", "provider"),)

    def __str__(self):
        return f"{self.get_provider_display()} — {self.user}"


class ReminderEventLink(models.Model):
    reminder = models.ForeignKey(
        Reminder, on_delete=models.CASCADE, related_name="event_links", verbose_name="Напоминание"
    )
    connection = models.ForeignKey(
        CalendarConnection,
        on_delete=models.CASCADE,
        related_name="event_links",
        verbose_name="Подключение",
    )
    external_event_id = models.CharField("ID события", max_length=512)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Связь с событием календаря"
        verbose_name_plural = "Связи с событиями календаря"
        unique_together = (("connection", "external_event_id"),)

    def __str__(self):
        return f"{self.connection.provider}:{self.external_event_id}"
