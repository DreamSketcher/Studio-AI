#!/usr/bin/env python3
"""Запуск PySide6 GUI для AI Studio.

Использование:
    python run_gui.py
"""
from __future__ import annotations

import sys


if __name__ == "__main__":
    try:
        from ai_studio_core.ui import run
    except ImportError as e:
        raise SystemExit(
            "PySide6 не установлен. Установите его:\n"
            "  pip install -e '.[gui]'\n"
            f"Оригинальная ошибка: {e}"
        )

    sys.exit(run())
