"""Каталог событий experience-слоя (уровень 1).

Событие — это факт, который УЖЕ произошёл в приложении (сигнал контроллера
или успешное действие окна). Новые события добавляются только сюда:
пресеты и менеджер валидируют имена по ALL_EVENTS — опечатка в пресете
выявляется при загрузке, а не молча игнорируется.
"""
from __future__ import annotations

APP_STARTED = "app_started"
GENERATION_COMPLETE = "generation_complete"
GENERATION_FAILED = "generation_failed"
QUEUE_DRAINED = "queue_drained"
PROJECT_SAVED = "project_saved"
PROJECT_LOADED = "project_loaded"
PROJECT_NEW = "project_new"
DOWNLOAD_FINISHED = "download_finished"
EXPORT_DONE = "export_done"
CHAT_REPLY = "chat_reply"

ALL_EVENTS = frozenset({
    APP_STARTED, GENERATION_COMPLETE, GENERATION_FAILED, QUEUE_DRAINED,
    PROJECT_SAVED, PROJECT_LOADED, PROJECT_NEW, DOWNLOAD_FINISHED,
    EXPORT_DONE, CHAT_REPLY,
})

# Известные действия пресетов (уровень 1): валидация схемы пресета.
ALL_ACTIONS = frozenset({"toast", "sound", "accent_pulse"})
