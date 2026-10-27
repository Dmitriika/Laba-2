"""Запуск программы из командной строки: python -m streamstats analyze ..."""

import argparse
import logging
import sys
from pathlib import Path

from streamstats.analysis import analyze_files
from streamstats.errors import CliConfigError, StreamStatsError
from streamstats.parsers import get_parser
from streamstats.report import build_report, save_report


def build_arg_parser() -> argparse.ArgumentParser:
    """Собирает описание команд для модуля argparse."""
    parser = argparse.ArgumentParser(
        prog="streamstats",
        description="Потоковый анализатор файлов событий (CSV и JSONL).",
    )
    # Команды: пока одна — analyze
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="прочитать файлы и сделать отчёт")
    analyze.add_argument("inputs", nargs="+", type=Path, help="входные файлы")
    analyze.add_argument("--format", required=True, choices=["csv", "jsonl"], help="формат входных файлов")
    analyze.add_argument("--output", required=True, type=Path, help="куда сохранить JSON-отчёт")
    analyze.add_argument(
        "--skip-invalid",
        action="store_true",
        help="пропускать плохие строки вместо остановки",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    """Выполняет команду analyze и возвращает код выхода."""
    parse_one = get_parser(args.format)  # тут же проверим, что формат нам знаком

    # Проверим, что файлы существуют, до начала анализа
    for path in args.inputs:
        if not path.is_file():
            raise CliConfigError(f"Файл не найден: {path}")

    stats = analyze_files(args.inputs, parse_one, skip_invalid=args.skip_invalid)

    report = build_report(stats)
    save_report(report, args.output)

    print(f"Готово! Событий: {stats.total_events}, пропущено строк: {stats.skipped_lines}.")
    print(f"Отчёт сохранён в {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Ловит наши ошибки и превращает их в понятные сообщения."""
    # WARNING — уровень логов: сюда попадут пропущенные строки из --skip-invalid
    logging.basicConfig(level=logging.WARNING, format="WARNING: %(message)s")

    try:
        args = build_arg_parser().parse_args(argv)
        return run(args)
    except SystemExit as exit_signal:
        # argparse сам печатает подсказку --help (код 0) или свою ошибку (код 2).
        # Просто передаём его код выхода дальше, не пряча и не подменяя.
        return int(exit_signal.code or 0)
    except StreamStatsError as error:
        # Все ошибки пакета выводим коротко и понятно, без длинного текста traceback
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
