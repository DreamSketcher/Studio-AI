"""Experience layer — событийный слой микро-обратной связи и статистики.

Уровень 1: события → пресеты действий (toast / звук / акцентный пульс).
Уровень 2: статистика использования → честные эвристики (стартовая вкладка).

Отделён от ядра: знает только про сигналы контроллеров и колбэки окна.
Никаких скрытых персистентных изменений — transient-эффекты без спроса,
персистентные предпочтения только через явные настройки пользователя.
"""
from .events import (
    ALL_EVENTS,
    APP_STARTED,
    CHAT_REPLY,
    DOWNLOAD_FINISHED,
    EXPORT_DONE,
    GENERATION_COMPLETE,
    GENERATION_FAILED,
    PROJECT_LOADED,
    PROJECT_NEW,
    PROJECT_SAVED,
    QUEUE_DRAINED,
)
from .manager import AccentPulse, ExperienceManager
from .stats import UsageStats, suggested_start_workspace

__all__ = [
    "ALL_EVENTS", "APP_STARTED", "CHAT_REPLY", "DOWNLOAD_FINISHED", "EXPORT_DONE",
    "GENERATION_COMPLETE", "GENERATION_FAILED", "PROJECT_LOADED", "PROJECT_NEW",
    "PROJECT_SAVED", "QUEUE_DRAINED",
    "AccentPulse", "ExperienceManager", "UsageStats", "suggested_start_workspace",
]
