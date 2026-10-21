from .base import CalendarProvider
from .google import GoogleCalendarProvider
from .yandex import YandexCalendarProvider


def get_provider(connection) -> CalendarProvider:
    """Фабрика провайдеров по типу подключения."""
    if connection.provider == "google":
        return GoogleCalendarProvider(connection)
    if connection.provider == "yandex":
        return YandexCalendarProvider(connection)
    raise ValueError(f"Неизвестный провайдер: {connection.provider}")


__all__ = ["CalendarProvider", "GoogleCalendarProvider", "YandexCalendarProvider", "get_provider"]
