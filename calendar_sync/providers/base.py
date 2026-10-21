"""Абстрактный провайдер календаря."""

from abc import ABC, abstractmethod


class CalendarProvider(ABC):
    """Единый интерфейс для Google Calendar и Яндекс Календаря."""

    def __init__(self, connection):
        self.connection = connection

    @abstractmethod
    def validate(self) -> str:
        """Проверяет подключение; возвращает идентификатор календаря по умолчанию."""

    @abstractmethod
    def list_events(self, since, until) -> list[dict]:
        """Список событий в диапазоне [since, until].

        Каждое событие — dict: {id, summary, start (aware datetime), rrule (str|None)}.
        """

    @abstractmethod
    def create_event(self, event: dict) -> str:
        """Создаёт событие; возвращает его внешний id."""

    @abstractmethod
    def update_event(self, external_id: str, event: dict) -> None:
        """Обновляет событие."""

    @abstractmethod
    def delete_event(self, external_id: str) -> None:
        """Удаляет событие."""
