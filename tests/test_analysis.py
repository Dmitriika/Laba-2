"""Тесты сбора статистики (analysis.py)."""

import pytest

from streamstats.analysis import analyze_files
from streamstats.errors import InvalidEventError
from streamstats.parsers import parse_csv, parse_jsonl

# Семь хороших строк JSONL. Разные уровни и источники, чтобы было что считать.
GOOD_JSONL = (
    '{"timestamp": "2024-01-15T10:30:00", "level": "INFO", "source": "api", "message": "ok"}\n'
    '{"timestamp": "2024-01-15T10:31:00", "level": "ERROR", "source": "db", "message": "ошибка 1"}\n'
    '{"timestamp": "2024-01-15T10:32:00", "level": "CRITICAL", "source": "db", "message": "беда"}\n'
    '{"timestamp": "2024-01-15T10:33:00", "level": "ERROR", "source": "api", "message": "ошибка 2"}\n'
    '{"timestamp": "2024-01-15T10:34:00", "level": "WARNING", "source": "disk", "message": "места мало"}\n'
    '{"timestamp": "2024-01-15T10:35:00", "level": "DEBUG", "source": "net", "message": "проверка связи"}\n'
    # у последней строки нет перевода строки в конце — так тоже должно работать
    '{"timestamp": "2024-01-15T10:36:00", "level": "ERROR", "source": "mail", "message": "smtp не отвечает"}'
)


def write(tmp_path, name, text):
    """Маленькая помощь: создать файл с текстом и вернуть путь к нему."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_statistics_counts(tmp_path):
    """Считаем всё сразу: уровни, источники, топ ошибок, первая и последняя метка."""
    path = write(tmp_path, "events.jsonl", GOOD_JSONL)

    stats = analyze_files([path], parse_jsonl)

    assert stats.total_events == 7
    assert stats.levels["ERROR"] == 3
    assert stats.levels["CRITICAL"] == 1
    assert stats.levels["INFO"] == 1
    assert stats.sources["db"] == 2
    # топ источников ошибок (ERROR + CRITICAL): db лидирует с 2 ошибками
    top = stats.top_error_sources(5)
    assert top[0] == ("db", 2)
    assert len(top) == 3
    assert stats.first_timestamp.isoformat() == "2024-01-15T10:30:00"
    assert stats.last_timestamp.isoformat() == "2024-01-15T10:36:00"
    assert stats.skipped_lines == 0


def test_top_error_sources_only_five(tmp_path):
    """В топе не больше пяти источников, даже если ошибочных источников шесть."""
    lines = []
    for number in range(6):
        lines.append(
            f'{{"timestamp": "2024-01-15T10:{number:02d}:00", "level": "ERROR",'
            f' "source": "сервис-{number}", "message": "ой"}}\n'
        )
    path = write(tmp_path, "many.jsonl", "".join(lines))

    stats = analyze_files([path], parse_jsonl)

    assert stats.total_events == 6
    assert len(stats.top_error_sources(5)) == 5


def test_stop_on_bad_line_by_default(tmp_path):
    """Без skip_invalid плохая строка останавливает работу; в тексте есть файл и строка."""
    bad = write(tmp_path, "bad.jsonl", GOOD_JSONL + "\n{сломанная строка}\n")

    with pytest.raises(InvalidEventError) as error:
        analyze_files([bad], parse_jsonl, skip_invalid=False)

    assert "bad.jsonl" in str(error.value)
    assert "строка 8" in str(error.value)


def test_skip_invalid_mode(tmp_path):
    """Со skip_invalid плохая строка пропускается, но статистика по хорошим считается."""
    bad = write(tmp_path, "bad.jsonl", "{сломанная}\n" + GOOD_JSONL)

    stats = analyze_files([bad], parse_jsonl, skip_invalid=True)

    assert stats.total_events == 7
    assert stats.skipped_lines == 1


def test_multiple_files_combined(tmp_path):
    """Несколько файлов одного формата дают общую статистику."""
    first = write(tmp_path, "one.jsonl", GOOD_JSONL)
    second = write(tmp_path, "two.jsonl", GOOD_JSONL)

    stats = analyze_files([first, second], parse_jsonl)

    assert stats.total_events == 14
    assert stats.levels["ERROR"] == 6
    assert stats.sources["db"] == 4
    assert stats.first_timestamp.isoformat() == "2024-01-15T10:30:00"


def test_unicode_messages(tmp_path):
    """Русский текст в сообщениях и источниках читается без проблем."""
    path = write(
        tmp_path,
        "unicode.csv",
        "timestamp,level,source,message\n"
        "2024-01-15T10:30:00,WARNING,сервер-А,Проверьте конфигурацию\n",
    )

    stats = analyze_files([path], parse_csv)

    assert stats.sources["сервер-А"] == 1
    assert stats.levels["WARNING"] == 1


def test_empty_file_gives_zero_stats(tmp_path):
    """Пустой файл — нулевая статистика, падать ничего не должно."""
    path = write(tmp_path, "empty.jsonl", "")

    stats = analyze_files([path], parse_jsonl)

    assert stats.total_events == 0
    assert stats.first_timestamp is None
    assert stats.last_timestamp is None
    assert stats.top_error_sources(5) == []
