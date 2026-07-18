"""Базовый контроллер — мост между UI и engine-слоем.

Принципы:
1. UI НИКОГДА не импортирует engine напрямую.
2. Контроллер переводит UI-действия в engine-вызовы.
3. Контроллер переводит engine-события в UI-обновления.
4. Тяжёлые операции выносятся в WorkerThread.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot


class WorkerThread(QThread):
    """Универсальный worker для фоновых задач."""
    progress = Signal(int, str)      # (percent, status_text)
    result = Signal(object)          # Результат
    error = Signal(str)
    finished_clean = Signal()

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def run(self) -> None:
        try:
            result = self._fn(
                *self._args,
                progress_callback=self._report_progress,
                cancel_check=lambda: self._cancelled,
                **self._kwargs,
            )
            if not self._cancelled:
                self.result.emit(result)
                self.finished_clean.emit()
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

    def cancel(self) -> None:
        self._cancelled = True

    def _report_progress(self, percent: int, status: str = "") -> None:
        self.progress.emit(int(percent), str(status))


class BaseController(QObject):
    busy_changed = Signal(bool)
    status_message = Signal(str)
    error_occurred = Signal(str)
    log_message = Signal(str, str)  # (level, message)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._active_worker: WorkerThread | None = None

    def _run_in_background(self, fn: Callable, *args, **kwargs) -> WorkerThread:
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.cancel()
            self._active_worker.wait(3000)

        worker = WorkerThread(fn, *args, **kwargs)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)
        self._active_worker = worker
        self.busy_changed.emit(True)
        worker.start()
        return worker

    def cancel_current(self) -> None:
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.cancel()

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self.error_occurred.emit(message)
        self.log_message.emit("ERROR", message)
        self.busy_changed.emit(False)

    @Slot()
    def _on_worker_finished(self) -> None:
        self.busy_changed.emit(False)
        self._active_worker = None
