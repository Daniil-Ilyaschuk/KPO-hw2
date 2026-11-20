import argparse

from infrastructure.console_ui import ConsoleUI
from services.container import build_container


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ПОС — консольное приложение преподавательской оценки студентов."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Запустить сквозной демонстрационный сценарий и завершить работу.",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Формат экспорта итоговой ведомости (по умолчанию: csv).",
    )
    parser.add_argument(
        "--export-path",
        default=None,
        help="Путь для сохранения файла ведомости в демо-режиме.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    container = build_container(export_format=args.format)
    ui = container.resolve(ConsoleUI)

    if args.demo:
        export_path = args.export_path or f"pos_demo_report.{args.format}"
        ui.run_demo(export_path=export_path)
    else:
        ui.run_interactive()


if __name__ == "__main__":
    main()