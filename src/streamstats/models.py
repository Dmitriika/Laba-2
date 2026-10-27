"""Модель события.

Событие — это одна запись из CSV или JSONL файла.
У события четыре обязательных поля:
timestamp, level, source, message.
"""

from dataclasses import dataclass
from datetime import datetime

from streamstats.errors import InvalidEventError, InvalidTimestampError

# Разрешённые уровни события. Порядок важен: так выведем в отчёте.
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass
class Event:
    """Одно событие (одна строка входного файла)."""

    timestamp: datetime  # уже превращённая из строки в дату
    level: str  # один из LEVELS
    source: str  # откуда событие, непустая строка
    message: str  # текст сообщения


def parse_timestamp(value: str) -> datetime:
    """Превращает строку вида '2024-01-15T10:30:00' в объект datetime.

    Если строка не читается — бросает InvalidTimestampError.
    """
    if not isinstance(value, str) or not value.strip():
        raise InvalidTimestampError(f"Пустая временная метка: {value!r}")
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        raise InvalidTimestampError(f"Время не в формате ISO 8601: {value!r}") from None


def make_event(timestamp: datetime, level: str, source: str, message: str) -> Event:
    """Создаёт Event и проверяет, что все поля правильные.

    Если что-то не так — бросает InvalidEventError.
    """
    if not isinstance(level, str) or level.strip().upper() not in LEVELS:
        raise InvalidEventError(f"Неизвестный уровень: {level!r}")
    if not isinstance(source, str) or not source.strip():
        raise InvalidEventError(f"Источник (source) не может быть пустым: {source!r}")
    if not isinstance(message, str):
        raise InvalidEventError(f"Сообщение (message) должно быть строкой: {message!r}")

    return Event(
        timestamp=timestamp,
        level=level.strip().upper(),
        source=source.strip(),
        message=message,
    )
