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

Это убирает ВСЕ синхронные `import torch`/`import TTS` с пути старта окна
MainWindow.__init__, из‑за которых битый torch убивал GUI‑процесс ещё до
window.show().
"""
from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

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


def _probe_cuda_in_torch() -> tuple[bool, str]:
    """Импортирует torch и смотрит torch.cuda.is_available().

    Вызывается ИСКЛЮЧИТЕЛЬНО из фонового потока (DiagnosticsBridge) ПОСЛЕ
    того как run_full_diagnostics подтвердила, что torch рабочий — т.е.
    в момент, когда import torch не должен уронить процесс. Даже если упадёт,
    это произойдёт в фоне и не повлияет на старт GUI.
    """
    try:
        import torch  # noqa: F811
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "CUDA"
            return True, name
        return False, ""
    except Exception:
        return False, ""


class DiagnosticsBridge(QObject):
    """Одиночный мост: один фоновый запуск диагностики, один сигнал."""

    diagnostics_updated = Signal()   # без аргументов: подписчики читают cached_results()
    cuda_info_changed = Signal(bool, str)  # (available, device_name)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._refresh_started = False
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
        """Запустить run_full_diagnostics в фоне (если ещё не запущен)."""
        if self._refresh_started and not force:
            return
        self._refresh_started = True
        bridge = self

        def _worker():
            try:
                results = run_full_diagnostics(force_refresh=force)
            except Exception as e:
                results = {"_error": str(e)}
            bridge._results = results or {}

            # Пока мы в фоне и знаем, что torch рабочий — безопасно
            # импортировать его для определения CUDA (не раньше).
            if results.get("torch") is True:
                cuda_ok, cuda_name = _probe_cuda_in_torch()
            else:
                cuda_ok, cuda_name = False, ""

            from PySide6.QtCore import QMetaObject, Qt

            def _apply():
                bridge._cuda_available = cuda_ok
                bridge._cuda_device_name = cuda_name
                bridge.cuda_info_changed.emit(cuda_ok, cuda_name)
                bridge.diagnostics_updated.emit()

            try:
                QMetaObject.invokeMethod(
                    bridge, "_apply_in_gui", Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                # invokeMethod с методом без аргументов работает стабильно
                # через QMetaObject в PySide6; если вызов не сработал —
                # откатываемся к прямому вызову (в худшем случае подписчики
                # получат сигнал из фонового потока, что безопасно для
                # большинства Qt‑операций чтения).
                _apply()

        threading.Thread(target=_worker, daemon=True, name="diag-refresh").start()

    @Slot()
    def _apply_in_gui(self) -> None:
        # Этот слот вызывается через QueuedConnection в GUI‑потоке после
        # завершения фоновой диагностики.
        # Повторно читаем кэш с диска (run_full_diagnostics уже сохранил его).
        try:
            self._results = load_diagnostics_cache()
        except Exception:
            pass


# Глобальный singleton, создаваемый по требованию (чтобы не требовался
# QApplication на момент импорта модуля).
_BRIDGE: Optional[DiagnosticsBridge] = None


def get_bridge() -> DiagnosticsBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = DiagnosticsBridge()
    return _BRIDGE
