"""Интеграционный тест: запускаем настоящую команду из командной строки."""

import json
import subprocess
import sys
from pathlib import Path

# пакет лежит в src, добавим эту папку к пути поиска модулей для дочернего процесса
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    """Выполняет python -m streamstats ... и возвращает результат запуска."""
    return subprocess.run(
        [sys.executable, "-m", "streamstats", *arguments],
        check=False,  # код выхода проверяем сами в тестах
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONPATH": SRC_DIR, "PATH": "/usr/bin:/bin"},
    )


def test_analyze_jsonl_writes_report(tmp_path):
    """Полный путь: вызываем CLI, на диске появляется JSON-отчёт со всеми полями."""
    data = tmp_path / "events.jsonl"
    data.write_text(
        '{"timestamp": "2024-01-15T10:30:00", "level": "INFO", "source": "api", "message": "ok"}\n'
        '{"timestamp": "2024-01-15T10:31:00", "level": "ERROR", "source": "db", "message": "упал"}\n',
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"

    result = run_cli("analyze", str(data), "--format", "jsonl", "--output", str(report_path))

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["total_events"] == 2
    assert report["levels"]["ERROR"] == 1
    assert report["top_error_sources"] == [{"source": "db", "count": 1}]
    assert report["first_timestamp"] == "2024-01-15T10:30:00"
    assert report["skipped_lines"] == 0


def test_bad_line_default_stops_with_code_2(tmp_path):
    """Без --skip-invalid: код выхода 2, в stderr имя файла и номер строки."""
    data = tmp_path / "broken.jsonl"
    data.write_text('{"bad json\n', encoding="utf-8")
    report_path = tmp_path / "report.json"

    result = run_cli("analyze", str(data), "--format", "jsonl", "--output", str(report_path))

    assert result.returncode == 2
    assert "broken.jsonl" in result.stderr
    assert "строка 1" in result.stderr
    # отчёт в этом случае не создаётся
    assert not report_path.exists()


def test_bad_line_skip_invalid_continues(tmp_path):
    """С --skip-invalid: код 0, плохая строка пропущена и записана в отчёт и в лог."""
    data = tmp_path / "mixed.csv"
    data.write_text(
        "timestamp,level,source,message\n"
        "2024-01-15T10:30:00,INFO,api,хорошая\n"
        "плохая,строка,тут,\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"

    result = run_cli(
        "analyze", str(data), "--format", "csv", "--output", str(report_path), "--skip-invalid"
    )

    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr  # предупреждение в лог
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["total_events"] == 1
    assert report["skipped_lines"] == 1


def test_missing_file_is_config_error(tmp_path):
    """Файла нет — CLI ругается понятно и выходит с кодом 2."""
    result = run_cli(
        "analyze", str(tmp_path / "nope.jsonl"),
        "--format", "jsonl", "--output", str(tmp_path / "r.json"),
    )

    assert result.returncode == 2
    assert "не найден" in result.stderr


def test_help_works():
    """python -m streamstats --help должен работать и выйти с кодом 0."""
    result = run_cli("--help")

    assert result.returncode == 0
    assert "usage:" in result.stdout
