"""Сбор статистики по событиям.

Statistics считает всё "на лету": события приходят по одному из парсера,
мы обновляем счётчики и тут же про них забываем. Поэтому памяти нужно
мало, даже если в файле миллионы строк.

Статистика нескольких файлов объединяется: события из всех файлов
считаем одними и теми же счётчиками.
"""

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from streamstats.errors import InvalidEventError
from streamstats.models import Event

# Наш собственный логгер: через него пишем предупреждения о пропущенных строках.
LOGGER = logging.getLogger("streamstats")


@dataclass
class Statistics:
    """Все числа, которые мы считим по событиям."""

    total_events: int = 0  # всего событий
    levels: Counter = field(default_factory=Counter)  # сколько событий каждого уровня
    sources: Counter = field(default_factory=Counter)  # сколько событий каждого источника
    error_sources: Counter = field(default_factory=Counter)  # источники уровней ERROR/CRITICAL
    first_timestamp: datetime | None = None  # самая ранняя метка
    last_timestamp: datetime | None = None  # самая поздняя метка
    skipped_lines: int = 0  # сколько строк пропущено (режим --skip-invalid)

    def add_event(self, event: Event) -> None:
        """Добавляет одно событие в статистику."""
        self.total_events += 1
        self.levels[event.level] += 1
        self.sources[event.source] += 1

        if event.level in ("ERROR", "CRITICAL"):
            self.error_sources[event.source] += 1

        # Запоминаем самую раннюю и самую позднюю временную метку
        if self.first_timestamp is None or event.timestamp < self.first_timestamp:
            self.first_timestamp = event.timestamp
        if self.last_timestamp is None or event.timestamp > self.last_timestamp:
            self.last_timestamp = event.timestamp

    def top_error_sources(self, count: int = 5) -> list[tuple[str, int]]:
        """Возвращает топ-N источников ошибок (уровни ERROR и CRITICAL).

        Результат — список пар (источник, число ошибок), от большего к меньшему.
        """
        return self.error_sources.most_common(count)


def analyze_files(
    paths: list[Path], parse_one: Callable, skip_invalid: bool = False
) -> Statistics:
    """Считает общую статистику по списку файлов.

    parse_one — функция-парсер (parse_csv или parse_jsonl): она читает файл
    построчно и отдаёт события по одному. Если строка плохая, парсер бросает
    InvalidEventError прямо во время перебора (в тексте уже есть номер строки).

    skip_invalid — что делать с плохой строкой:
        False: остановить обработку и пустить ошибку выше (CLI выйдет с кодом 2);
        True: пропустить строку, записать WARNING в лог, посчитать её в skipped_lines
              и продолжить читать файл дальше.
    """
    stats = Statistics()

    for path in paths:
        # parse_one вернёт генератор: он читает файл построчно и отдаёт
        # по одной строке за раз (ParsedLine из parsers.py).
        stream = parse_one(path)
        for parsed in stream:
            if parsed.event is not None:
                stats.add_event(parsed.event)
                continue
            # Строка плохая — решаем, что с ней делать.
            message = f"Файл {path}, строка {parsed.line_number}: {parsed.error_text}"
            if not skip_invalid:
                # Режим по умолчанию: останавливаем обработку (CLI выйдет с кодом 2).
                raise InvalidEventError(message)
            # Режим --skip-invalid: пропускаем строку, пишем WARNING в лог
            # и добавляем число пропущенных строк в статистику (оно попадёт в отчёт).
            stats.skipped_lines += 1
            LOGGER.warning("%s — строка пропущена", message)

    return stats
