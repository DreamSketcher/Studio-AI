# -*- coding: utf-8 -*-
"""engine/env_core/install_state.py — глобальное состояние установки пакетов.

Вынесен из engine/gui/env_settings.py на Этапе A (исправление нарушений #1–#3
по ТЗ на извлечение env-движка): функции лока/состояния установки по смыслу
относятся к слою env_core, а не к GUI-слою.

GUI-обвязка (engine/gui/env_settings.py) продолжает видеть эти имена через
re-export в том же модуле — ни один вызов в engine/gui/* не меняется.
"""

from __future__ import annotations

import threading

# ── ГЛОБАЛЬНЫЙ ЛОК УСТАНОВКИ (предотвращает одновременные pip install) ──
# Используется всеми точками входа: startup recovery, settings buttons,
# rvc_setup, torch_setup, llama_setup.
_INSTALL_LOCK = threading.RLock()
_INSTALL_STATE = {"running": False, "type": None, "cancelled": False}


def _acquire_install_lock(install_type: str) -> bool:
    """Пытается захватить лок установки.
    Возвращает True если лок получен, False если другая установка уже идёт.
    """
    global _INSTALL_STATE
    acquired = _INSTALL_LOCK.acquire(blocking=False)
    if acquired:
        _INSTALL_STATE = {"running": True, "type": install_type, "cancelled": False}
        return True
    return False


def _release_install_lock():
    """Освобождает лок установки."""
    global _INSTALL_STATE
    _INSTALL_STATE = {"running": False, "type": None, "cancelled": False}
    _INSTALL_LOCK.release()


def _is_install_running() -> bool:
    """Проверяет, идёт ли какая-то установка."""
    return _INSTALL_STATE.get("running", False)


def _get_current_install_type() -> str:
    """Возвращает тип текущей установки или пустую строку."""
    return _INSTALL_STATE.get("type", "")


def _set_install_cancelled():
    """Помечает текущую установку как отменённую."""
    _INSTALL_STATE["cancelled"] = True


# Флаг для защиты clear_diagnostics_cache — не очищать, если идёт восстановление/установка
def _can_clear_diagnostics_cache() -> bool:
    """Возвращает True если можно безопасно очистить кэш диагностики."""
    return not _is_install_running()
