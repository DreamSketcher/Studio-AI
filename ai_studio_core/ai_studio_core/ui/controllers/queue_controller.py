"""Контроллер очереди задач."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Signal

from .base_controller import BaseController


@dataclass
class QueueTask:
    id: str
    type: str           # "tts" / "chat" / "batch" / ...
    model: str
    status: str = "queued"   # queued/running/done/error/cancelled
    progress: int = 0
    output: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


class QueueController(BaseController):
    queue_changed = Signal(list)
    task_added = Signal(str)
    task_updated = Signal(str)
    task_removed = Signal(str)

    def __init__(self):
        super().__init__()
        self._tasks: dict[str, QueueTask] = {}
        # Две демо-задачи для отображения
        self._add_demo()

    def _add_demo(self) -> None:
        from uuid import uuid4
        t1 = QueueTask(id=str(uuid4())[:6], type="TTS", model="XTTS v2", status="running", progress=45)
        t2 = QueueTask(id=str(uuid4())[:6], type="TTS", model="XTTS v2", status="queued", progress=0)
        for t in (t1, t2):
            self._tasks[t.id] = t

    def add_task(self, type_: str, model: str, params: dict | None = None) -> str:
        from uuid import uuid4
        task = QueueTask(
            id=str(uuid4())[:6],
            type=type_,
            model=model,
            params=params or {},
        )
        self._tasks[task.id] = task
        self.task_added.emit(task.id)
        self.queue_changed.emit(list(self._tasks.values()))
        self.status_message.emit(f"Task added: {task.id} ({type_})")
        return task.id

    def cancel_task(self, task_id: str) -> None:
        if task_id in self._tasks:
            self._tasks[task_id].status = "cancelled"
            self.task_updated.emit(task_id)
            self.queue_changed.emit(list(self._tasks.values()))

    def clear_completed(self) -> None:
        to_remove = [tid for tid, t in self._tasks.items() if t.status in ("done", "error", "cancelled")]
        for tid in to_remove:
            del self._tasks[tid]
            self.task_removed.emit(tid)
        self.queue_changed.emit(list(self._tasks.values()))

    def tasks(self) -> list[QueueTask]:
        return list(self._tasks.values())

    def set_task_progress(self, task_id: str, percent: int, status: str = "running") -> None:
        if task_id in self._tasks:
            t = self._tasks[task_id]
            t.progress = percent
            t.status = status
            self.task_updated.emit(task_id)

    def running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "running")

    def queued_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "queued")
