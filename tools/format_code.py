#!/usr/bin/env python3
"""Форматирование и линт кода по стандарту проекта.

Стандарт зафиксирован в ``pyproject.toml`` одного уровня с папкой ``tools/``:

* форматтер **Black**      — line-length 100, target py310/py311;
* линтер   **Ruff**        — line-length 100, правила E/F/W,
  исключения (E501, E401, E402, E741, F401, F403, F405, F811, F841)
  берутся из ``[tool.ruff.lint].ignore`` — здесь они НЕ дублируются,
  оба инструмента читают pyproject.toml сами.

Использование (из любого каталога):

    python tools/format_code.py            # авто-правка: ruff --fix + black
    python tools/format_code.py --check    # только проверка (для CI / pre-commit)

Код выхода: 0 — всё чисто/исправлено; 1 — найдены нарушения (--check)
или инструменты не установлены.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # корень проекта (там pyproject.toml)
# Что форматируем/линтим: пакет, тесты, инструменты, точки входа.
TARGETS = ["ai_studio_core", "test", "tools", "run_gui.py"]


def _run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    targets = [t for t in TARGETS if (ROOT / t).exists()]

    if not targets:
        print("Не найдено ни одной цели для проверки — запустите из репозитория проекта.")
        return 1

    missing = [m for m in ("ruff", "black") if shutil.which(m) is None]
    if missing:
        print(
            "Не установлены инструменты: " + ", ".join(missing) + "\n"
            "Установите:  python -m pip install \"ruff>=0.6\" \"black>=24\"\n"
            "(или все dev-зависимости: python -m pip install -e \".[dev]\")"
        )
        return 1

    rc = 0

    if check:
        # CI-режим: ничего не меняем, только отчёт.
        rc |= _run([sys.executable, "-m", "ruff", "check", *targets])
        rc |= _run([sys.executable, "-m", "black", "--check", "--diff", *targets])
        if rc:
            print("\nНарушения стандарта. Исправить автоматически:"
                  " python tools/format_code.py")
        else:
            print("\nСтиль: OK — Black (100 симв.) и Ruff E/F/W нарушений не нашли.")
    else:
        # Рабочий режим: ruff чинит что умеет, затем black выравнивает формат.
        rc |= _run([sys.executable, "-m", "ruff", "check", "--fix", *targets])
        rc |= _run([sys.executable, "-m", "black", *targets])
        if rc == 0:
            print("\nГотово. Прогоните тесты перед коммитом.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
