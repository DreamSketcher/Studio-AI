"""Статистика использования (уровень 2) — честная аналитика без ИИ.

Счётчики только из реальных событий приложения; персистентность —
атомарный JSON (`json/usage_stats.json`, monkeypatch'ится `STATS_PATH`).
Эвристики — детерминированные и объяснимые: причина решения всегда
возвращается вместе с ним и озвучивается в лог.
"""
from __future__ import annotations

import os

from ai_studio_core.atomic_write import atomic_write_json
from ai_studio_core.paths import JSON_DIR

STATS_PATH = os.path.join(JSON_DIR, "usage_stats.json")

WORKSPACES = ("tts", "chat", "image", "pipeline")
MIN_ACTIVATIONS_FOR_HEURISTIC = 3


class UsageStats:
    """Счётчики сессий/активаций/действий. Никакой телеметрии — локальный JSON."""

    def __init__(self, data: dict | None = None, path: str | None = None):
        self._path = path or STATS_PATH
        base = {
            "version": 1,
            "sessions": 0,
            "session_seconds_total": 0.0,
            "workspace_activations": {w: 0 for w in WORKSPACES},
            "actions": {},
            "backend_use": {},
        }
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "workspace_activations" and isinstance(value, dict):
                    base[key].update({k: int(v) for k, v in value.items()
                                      if k in base[key]})
                elif key in base and isinstance(value, type(base[key])):
                    base[key] = value
        self._d = base

    # ── запись фактов ──

    def record_session(self) -> None:
        self._d["sessions"] += 1

    def record_active_seconds(self, seconds: float) -> None:
        try:
            self._d["session_seconds_total"] += max(0.0, float(seconds))
        except (TypeError, ValueError):
            pass

    def record_activation(self, workspace_id: str) -> None:
        if workspace_id in self._d["workspace_activations"]:
            self._d["workspace_activations"][workspace_id] += 1

    def record_action(self, action: str) -> None:
        acts = self._d["actions"]
        acts[action] = int(acts.get(action, 0)) + 1

    def record_backend(self, backend: str) -> None:
        if backend:
            bu = self._d["backend_use"]
            bu[backend] = int(bu.get(backend, 0)) + 1
            self._d["last_backend"] = backend

    # ── чтение ──

    def data(self) -> dict:
        import copy
        return copy.deepcopy(self._d)

    def activations(self) -> dict:
        return dict(self._d["workspace_activations"])

    # ── персистентность ──

    @classmethod
    def load(cls, path: str | None = None) -> "UsageStats":
        import json
        path = path or STATS_PATH
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
        return cls(data, path=path)

    def save(self, path: str | None = None) -> None:
        atomic_write_json(path or self._path, self._d)


def suggested_start_workspace(stats: UsageStats, default: str = "tts",
                              min_activations: int = MIN_ACTIVATIONS_FOR_HEURISTIC
                              ) -> tuple[str, str]:
    """Эвристика стартовой вкладки: максимум активаций побеждает.

    Возвращает (workspace_id, причина). Причину честно показываем в логе —
    правило прозрачно: счётчики пользователя, не «ИИ решил».
    """
    acts = stats.activations()
    total = sum(acts.values())
    if total < min_activations:
        return default, f"недостаточно данных ({total}/{min_activations})"
    best = max(acts.items(), key=lambda kv: kv[1])
    if acts.get(default, 0) == best[1]:
        # ничья — честный дефолт
        return default, f"ничья ({best[1]} активаций), дефолт {default}"
    if best[1] == total:
        return best[0], f"единственная используемая ({best[1]}/{total})"
    return best[0], f"{best[1]}/{total} активаций — чаще всего"
