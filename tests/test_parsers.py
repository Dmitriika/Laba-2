"""Юнит-тесты для обоих парсеров (CSV и JSONL)."""

from datetime import datetime

import pytest

from streamstats.errors import UnsupportedFormatError
from streamstats.models import Event
from streamstats.parsers import get_parser, parse_csv, parse_jsonl


def test_parse_csv_ok(tmp_path):
    """Парсер CSV читает заголовок и превращает строки в события."""
    path = tmp_path / "events.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2024-01-15T10:30:00,INFO,api,Запрос выполнен\n"
        "2024-01-15T10:31:00,ERROR,db,Соединение потеряно\n",
        encoding="utf-8",
    )

    lines = list(parse_csv(path))

    assert lines[0].event == Event(
        datetime(2024, 1, 15, 10, 30), "INFO", "api", "Запрос выполнен"
    )
    assert lines[1].event == Event(
        datetime(2024, 1, 15, 10, 31), "ERROR", "db", "Соединение потеряно"
    )


def test_parse_jsonl_ok(tmp_path):
    """Парсер JSONL читает каждую строку как отдельный JSON-объект."""
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"timestamp": "2024-01-15T10:30:00", "level": "info", "source": "api", "message": "ok"}\n'
        '{"timestamp": "2024-01-15T10:32:00", "level": "CRITICAL", "source": "db", "message": "упал"}\n',
        encoding="utf-8",
    )

    lines = list(parse_jsonl(path))

    assert len(lines) == 2
    # уровень приводим к верхнему регистру: info -> INFO
    assert lines[0].event.level == "INFO"
    assert lines[1].event == Event(datetime(2024, 1, 15, 10, 32), "CRITICAL", "db", "упал")


def test_parse_csv_empty_file(tmp_path):
    """В файле только заголовок — событий нет, но и ошибки тоже."""
    path = tmp_path / "empty.csv"
    path.write_text("timestamp,level,source,message\n", encoding="utf-8")

    assert list(parse_csv(path)) == []


def test_parse_jsonl_empty_file(tmp_path):
    """Пустой JSONL-файл — это ноль событий, а не ошибка."""
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    assert list(parse_jsonl(path)) == []


def test_parse_csv_bad_line(tmp_path):
    """Строка без колонки level — плохая: парсер отдаёт её с текстом ошибки."""
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,level,source,message\n"
        "2024-01-15T10:30:00,INFO,api,хорошая\n"
        "2024-01-15T10:31:00,,api,нет уровня\n",
        encoding="utf-8",
    )

    lines = list(parse_csv(path))

    bad = lines[1]  # вторая выданная строка (в файле это строка 3)
    assert bad.event is None
    assert bad.line_number == 3
    assert "уровень" in bad.error_text


def test_parse_jsonl_bad_line(tmp_path):
    """Сломанный JSON в строке — парсер отдаёт ошибку, но читает дальше."""
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '{"timestamp": "2024-01-15T10:30:00", "level": "INFO", "source": "api", "message": "ok"}\n'
        "{сломанная строка}\n",
        encoding="utf-8",
    )

    lines = list(parse_jsonl(path))

    assert len(lines) == 2
    bad = lines[1]
    assert bad.event is None
    assert bad.line_number == 2
    assert "JSON" in bad.error_text


def test_parse_bad_timestamp(tmp_path):
    """Временная метка не по ISO 8601 — событие не проходит проверку."""
    path = tmp_path / "bad_time.jsonl"
    path.write_text(
        '{"timestamp": "15.01.2024 10:30", "level": "INFO", "source": "api", "message": "ok"}\n',
        encoding="utf-8",
    )

    lines = list(parse_jsonl(path))

    assert lines[0].event is None
    assert "ISO 8601" in lines[0].error_text


def test_get_parser_unknown_format():
    """Неизвестный формат — отдельная ошибка UnsupportedFormatError."""
    assert get_parser("csv") is parse_csv
    assert get_parser("jsonl") is parse_jsonl

    with pytest.raises(UnsupportedFormatError):
        get_parser("xml")
