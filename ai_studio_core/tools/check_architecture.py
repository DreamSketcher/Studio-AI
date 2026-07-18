#!/usr/bin/env python3
"""check_architecture.py — запуск архитектурных валидаций для ai_studio_core.

Последовательно запускает import-linter и завершается кодом 0, если все
контракты соблюдены, и ненулевым кодом с пояснением при нарушении.

Назначение: вызывается из CI (architecture_gate.yml) как быстрый
архитектурный гейт, блокирующий PR, которые ломают слоистую архитектуру
(например, добавляют импорт TTS в env_core или обратно).
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    config = repo_root / ".importlinter"
    if not config.exists():
        print(f"[check_architecture] FATAL: .importlinter не найден в {repo_root}", file=sys.stderr)
        return 2

    # import-linter предоставляет CLI-функцию в importlinter.cli.lint_imports_command.
    # Вызываем её напрямую, а не через subprocess, чтобы не зависеть от того,
    # установлен ли скрипт lint-imports на PATH.
    try:
        from importlinter.cli import lint_imports_command
    except ImportError:
        print(
            "[check_architecture] FATAL: import-linter не установлен. "
            "Установите: pip install import-linter",
            file=sys.stderr,
        )
        return 2

    sys.argv = ["lint-imports", "--config", str(config)]
    try:
        rc = lint_imports_command()
    except SystemExit as e:
        rc = e.code
    rc = 0 if rc is None else int(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
