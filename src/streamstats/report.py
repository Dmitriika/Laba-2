"""Превращает собранную статистику в JSON-отчёт и сохраняет его в файл."""

import json
from pathlib import Path

from streamstats.analysis import Statistics


def build_report(stats: Statistics) -> dict:
    """Делает из статистики обычный словарь, который можно сохранить как JSON."""
    return {
        "total_events": stats.total_events,
        "levels": dict(stats.levels),
        "sources": dict(stats.sources),
        "top_error_sources": [
            {"source": source, "count": count}
            for source, count in stats.top_error_sources(5)
        ],
        "first_timestamp": (
            stats.first_timestamp.isoformat() if stats.first_timestamp else None
        ),
        "last_timestamp": (
            stats.last_timestamp.isoformat() if stats.last_timestamp else None
        ),
        "skipped_lines": stats.skipped_lines,
    }


def save_report(report: dict, output_path: Path) -> None:
    """Сохраняет отчёт в JSON-файл.

    ensure_ascii=False — чтобы русские слова в файле остались читаемыми.
    indent=2 — чтобы файл было удобно смотреть глазами.
    """
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
