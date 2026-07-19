#!/usr/bin/env python3
"""Запуск PySide6 GUI для AI Studio.

Использование:
    python run_gui.py

Отладочные выключатели (переменные окружения, для изоляции падений):
    AI_STUDIO_NO_QSS=1  — без stylesheet и тёмной палитры;
    AI_STUDIO_NO_DIAG=1 — без фоновой диагностики env_core;
    AI_STUDIO_NO_XP=1   — без experience-слоя (звуки/пульсы/статистика);
    AI_STUDIO_NO_PS=1   — без периодического опроса psutil в статус-баре.

Fatal-дампы нативных падений пишутся в logs/crash_dump.txt (и на stderr —
на stderr они появляются только если файл открыть не удалось).
"""
from __future__ import annotations

import sys

_CRASH_LOG = None  # держим ссылку, чтобы файл не закрылся GC


def _enable_crash_log() -> None:
    """faulthandler -> logs/crash_dump.txt.

    Windows fatal exception происходит в нативном коде (Qt/драйверы) — обычный
    traceback его не поймает. faulthandler на fatal-событии печатает стеки
    всех Python-потоков; сохраняем их в файл для расследования.
    """
    global _CRASH_LOG
    try:
        import faulthandler
        from datetime import datetime
        from pathlib import Path

        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        _CRASH_LOG = open(log_dir / "crash_dump.txt", "a", encoding="utf-8")
        _CRASH_LOG.write(f"\n===== запуск {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        _CRASH_LOG.flush()
        faulthandler.enable(_CRASH_LOG)
    except Exception:
        import faulthandler
        try:
            faulthandler.enable()  # fallback: stderr
        except Exception:
            pass


if __name__ == "__main__":
    _enable_crash_log()
    try:
        from ai_studio_core.ui import run
    except ImportError as e:
        raise SystemExit(
            "PySide6 не установлен. Установите его:\n"
            "  pip install -e '.[gui]'\n"
            f"Оригинальная ошибка: {e}"
        )

    sys.exit(run())
