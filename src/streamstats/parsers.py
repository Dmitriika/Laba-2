"""Чтение файлов построчно (это и есть 'потоковый' режим).

Мы никогда не читаем файл целиком в память: ни read(), ни readlines().
Функция-генератор отдаёт строки по одной, сколько бы строк в файле ни было.

CSV-файл: первая строка — заголовок с именами колонок, дальше строки с событиями.
Нужные колонки: timestamp, level, source, message.

JSONL-файл: каждая непустая строка — отдельный JSON-объект с теми же полями.

Плохая строка НЕ останавливает чтение: парсер выдаёт ParsedLine с текстом
ошибки, а что с ней делать (остановиться или пропустить) решает analysis.py.
"""

import csv
import json
from collections.abc import Iterator
from pathlib import Path

from streamstats.errors import InvalidEventError, UnsupportedFormatError
from streamstats.models import Event, make_event, parse_timestamp


class ParsedLine:
    """Одна прочитанная строка файла.

    Нужен ровно один из двух наборов полей:
      (line_number, event) — строка хорошая, событие разобрано;
      (line_number, None, error_text) — строка плохая, в error_text почему.
    """

    def __init__(self, line_number: int, event: Event | None = None,
                 error_text: str | None = None):
        self.line_number = line_number
        self.event = event
        self.error_text = error_text


# Поля, которые обязаны быть в каждой записи.
REQUIRED_FIELDS = ("timestamp", "level", "source", "message")


def _event_from_dict(data: dict) -> Event:
    """Превращает словарь (одна запись из CSV или JSONL) в событие Event."""
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            raise InvalidEventError(f"Нет обязательного поля: {field!r}")

    timestamp = parse_timestamp(data["timestamp"])
    return make_event(
        timestamp=timestamp,
        level=data["level"],
        source=data["source"],
        message=data["message"],
    )


def parse_csv(path: Path) -> Iterator[ParsedLine]:
    """Построчно читает CSV-файл и выдаёт строки (ParsedLine).

    Хорошая строка -> ParsedLine(номер, событие).
    Плохая строка  -> ParsedLine(номер, None, текст ошибки); чтение продолжается.
    """
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)  # DictReader сам прочитает строку-заголовок
        for row in reader:  # вот здесь идёт чтение построчно, а не всего файла
            line_number = reader.line_num  # номер текущей строки (1 — это заголовок)
            # row может содержать None-ключ, если колонок больше, чем в заголовке
            data = {key: value for key, value in row.items() if key is not None}
            try:
                event = _event_from_dict(data)
            except InvalidEventError as error:
                yield ParsedLine(line_number, None, str(error))
                continue
            yield ParsedLine(line_number, event)


def parse_jsonl(path: Path) -> Iterator[ParsedLine]:
    """Построчно читает JSONL-файл и выдаёт строки (ParsedLine).

    Правила те же, что у parse_csv: плохая строка не останавливает чтение.
    """
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):  # читаем по одной строке за раз
            line = line.strip()
            if not line:
                continue  # пустые строки просто пропускаем
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                yield ParsedLine(line_number, None, f"не получился JSON ({error})")
                continue
            if not isinstance(data, dict):
                yield ParsedLine(line_number, None, "ожидался объект {...}")
                continue
            try:
                event = _event_from_dict(data)
            except InvalidEventError as error:
                yield ParsedLine(line_number, None, str(error))
                continue
            yield ParsedLine(line_number, event)


def get_parser(fmt: str):
    """Возвращает функцию-парсер по имени формата ('csv' или 'jsonl')."""
    if fmt == "csv":
        return parse_csv
    if fmt == "jsonl":
        return parse_jsonl
    raise UnsupportedFormatError(f"Неизвестный формат: {fmt!r}. Нужно csv или jsonl.")
