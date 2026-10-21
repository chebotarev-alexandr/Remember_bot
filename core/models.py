"""Модели: пользователи Telegram и их напоминания."""

from django.db import models


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    username = models.CharField("Username", max_length=64, blank=True)
    first_name = models.CharField("Имя", max_length=64, blank=True)
    last_name = models.CharField("Фамилия", max_length=64, blank=True)
    timezone = models.CharField("Часовой пояс", max_length=64, default="UTC")
    is_premium = models.BooleanField("Премиум", default=False)
    is_blocked = models.BooleanField("Заблокирован", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        name = self.first_name or self.username or str(self.telegram_id)
        return f"{name} ({self.telegram_id})"


class Reminder(models.Model):
    class Kind(models.TextChoices):
        ONCE = "once", "Однократное"
        DAILY = "daily", "Ежедневное"
        WEEKLY = "weekly", "Еженедельное"
        MONTHLY = "monthly", "Ежемесячное"

    user = models.ForeignKey(
        TelegramUser, on_delete=models.CASCADE, related_name="reminders", verbose_name="Пользователь"
    )
    text = models.CharField("Текст", max_length=255)
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices)

    # Однократное — точный момент (aware, UTC)
    remind_at = models.DateTimeField("Напомнить в", null=True, blank=True)
    # Регулярное — локальное время дня (в поясе пользователя)
    time = models.TimeField("Время", null=True, blank=True)
    # Еженедельное — дни недели (список 0=пн .. 6=вс)
    weekdays = models.JSONField("Дни недели", default=list, blank=True)
    # Ежемесячное — число месяца (1-31)
    day_of_month = models.PositiveSmallIntegerField("Число месяца", null=True, blank=True)

    is_active = models.BooleanField("Активно", default=True)
    last_sent_at = models.DateTimeField("Последняя отправка", null=True, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Напоминание"
        verbose_name_plural = "Напоминания"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.text[:40]}"
