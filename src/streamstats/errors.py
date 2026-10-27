"""Ошибки пакета streamstats.

Все наши ошибки наследуются от StreamStatsError.
Это удобно: на границе CLI можно поймать одну ошибку и вывести понятное сообщение.
"""


class StreamStatsError(Exception):
    """Базовая ошибка пакета."""


class UnsupportedFormatError(StreamStatsError):
    """Запрошен формат, который мы не умеем читать (не csv и не jsonl)."""


class InvalidEventError(StreamStatsError):
    """Строка не является правильным событием: нет нужных полей или значения неверные."""


class InvalidTimestampError(InvalidEventError):
    """Поле timestamp не читается как дата в формате ISO 8601."""


class CliConfigError(StreamStatsError):
    """Пользователь вызвал команду неправильно (например, не указал файлы)."""
