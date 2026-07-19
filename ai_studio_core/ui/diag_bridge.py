# -*- coding: utf-8 -*-
"""ui/diag_bridge.py — мост между GUI и env_core.diagnostics.

Назначение:
  * Дать GUI‑слою синхронные, НЕ ИМПОРТИРУЮЩИЕ torch/TTS предикаты
    вида coqui_available() / diffusers_available(), работающие поверх
    закэшированного результата run_full_diagnostics().
  * Предоставить один фоновый запуск run_full_diagnostics() (в рабочем
    потоке, без блокировки UI), который по завершении испускает Qt‑сигнал,
    чтобы все подписчики (селекторы моделей, статус‑бар, визард, панель
    настроек) перечитали кэш и перерисовались.

КРИТИЧЕСКОЕ ПРАВИЛО: в ЭТОМ процессе (GUI) torch/TTS/CUDA не импортируются
НИКОГДА — ни на старте окна, ни в фоновом потоке. Access violation при
импорте битого torch убивает процесс целиком из любого потока, поэтому
«перенести импорт в поток» нельзя — можно только перенести его в другой
процесс. Все импорты (включая опрос CUDA) делает изолированный сабпроцесс
внутри env_core.diagnostics.run_full_diagnostics(); GUI читает только
JSON-результаты (поля cuda_available/cuda_name).
"""
from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, Signal, Slot

from ai_studio_core.env_core.diagnostics import (
    load_diagnostics_cache,
    run_full_diagnostics,
)


def _cache_says_ok(component: str) -> bool:
    """True, если в кэше диагностики компонент == True (т.е. работает)."""
    try:
        cache = load_diagnostics_cache()
    except Exception:
        return False
    return cache.get(component) is True


def torch_available() -> bool:
    """Доступен ли torch по последней диагностике? БЕЗ импорта torch."""
    return _cache_says_ok("torch")


def tts_available() -> bool:
    """Доступен ли Coqui TTS по последней диагностике? БЕЗ импорта TTS/torch."""
    return _cache_says_ok("tts") and _cache_says_ok("torch")


def coqui_available() -> bool:
    """Синоним для tts_available() — используется в TTSController."""
    return tts_available()


def diffusers_available() -> bool:
    """Stable‑Diffusion бэкенд доступен? Требуется torch + diffusers.

    diffusers не входит в число компонентов run_full_diagnostics, поэтому
    факт установки модуля diffusers проверяется отдельным лёгким импортом
    (diffusers не тянет нативные .so/.dll torch'а и не умеет уронить
    процесс на старте). Если torch в кэше не помечен как рабочий —
    сразу возвращаем False без импорта diffusers.
    """
    if not _cache_says_ok("torch"):
        return False
    try:
        import diffusers  # noqa: F401
        return True
    except Exception:
        return False


class DiagnosticsBridge(QObject):
    """Одиночный мост: один фоновый запуск диагностики, два сигнала.

    Сигналы (diagnostics_updated / cuda_info_changed) испускаются строго
    из GUI‑потока через QueuedConnection-слот _apply_in_gui — подписчики
    могут безопасно трогать виджеты. Сам QObject создаётся в GUI‑потоке
    (get_bridge() вызывается из конструкторов виджетов), поэтому queued
    доставка гарантирована его очередью событий.
    """

    diagnostics_updated = Signal()        # подписчики читают cached_results()
    cuda_info_changed = Signal(bool, str)  # (available, device_name)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._refresh_started = False
        self._running = False
        self._results: dict = {}
        self._cuda_available: bool = False
        self._cuda_device_name: str = ""

    # ── Чтение кэша ──
    def cached_results(self) -> dict:
        if not self._results:
            try:
                self._results = load_diagnostics_cache()
            except Exception:
                self._results = {}
        return dict(self._results)

    def component_ok(self, name: str) -> bool:
        return self.cached_results().get(name) is True

    def cuda_available(self) -> bool:
        return self._cuda_available

    def cuda_device_name(self) -> str:
        return self._cuda_device_name

    # ── Фоновый запуск ──
    def kickoff_refresh(self, force: bool = False) -> None:
        """Запустить run_full_diagnostics в фоне.

        Повторные вызовы: без force — только один раз за жизнь моста;
        c force — разрешены, но не одновременно с уже идущей проверкой
        (два сабпроцесса-пробы, пишущих один cache-файл, нам не нужны).
        """
        if self._refresh_started and not force:
            return
        if self._running:
            return
        self._refresh_started = True
        self._running = True
        bridge = self

        def _worker():
            try:
                results = run_full_diagnostics(force_refresh=force)
            except Exception as e:
                results = {"_error": str(e)}
            bridge._results = results or {}
            bridge._running = False
            # ВАЖНО: здесь НЕТ импорта torch/CUDA и быть не должно —
            # всё это уже сделал изолированный сабпроцесс диагностики,
            # а мост читает cuda_available/cuda_name из JSON-результата.
            try:
                QMetaObject.invokeMethod(
                    bridge, "_apply_in_gui", Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                # Нет очереди событий (не GUI-режим) — просто не эмитим.
                pass

        threading.Thread(target=_worker, daemon=True, name="diag-refresh").start()

    @Slot()
    def _apply_in_gui(self) -> None:
        # Выполняется в GUI‑потоке (QueuedConnection) после завершения
        # фоновой диагностики. Читаем результат (или кэш с диска),
        # обновляем CUDA‑поля и ТОЛЬКО ЗДЕСЬ испускаем сигналы —
        # подписчики получают их в GUI‑потоке и могут трогать виджеты.
        if not self._results:
            try:
                self._results = load_diagnostics_cache()
            except Exception:
                pass
        res = self._results or {}
        self._cuda_available = res.get("cuda_available") is True
        name = res.get("cuda_name")
        self._cuda_device_name = name if isinstance(name, str) else ""
        self.cuda_info_changed.emit(self._cuda_available, self._cuda_device_name)
        self.diagnostics_updated.emit()


# Глобальный singleton, создаваемый по требованию (чтобы не требовался
# QApplication на момент импорта модуля). Создаётся в GUI‑потоке —
# get_bridge() вызывается только из GUI‑кода (виджеты/окна/диалоги).
_BRIDGE: Optional[DiagnosticsBridge] = None


def get_bridge() -> DiagnosticsBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = DiagnosticsBridge()
    return _BRIDGE
