"""Пресеты experience-слоя: событие → действия (toast/звук/акцент).

Формат JSON:
{
  "name": "default",
  "events": {
    "generation_complete": {
      "toast": {"variant": "success", "text": "exp_msg_or_literal {output}"},
      "sound": "done_chime",
      "accent_pulse": {"color": "#10b981", "duration_ms": 900}
    }
  }
}

Валидация при загрузке: неизвестное событие/действие/звук/вариант →
ValueError с указанием места (не молчим и не «угадываем»).
"""
from __future__ import annotations

import json
import os

from .events import ALL_ACTIONS, ALL_EVENTS
from .sounds import available_tones

DEFAULT_PRESET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "theme", "presets", "experience.default.json",
)

_TOAST_VARIANTS = {"info", "success", "warning", "error"}


def validate_preset(data: dict) -> dict:
    """Нормализует и проверяет пресет. Возвращает mapping event→actions."""
    if not isinstance(data, dict):
        raise ValueError("preset root must be an object")
    events = data.get("events")
    if not isinstance(events, dict):
        raise ValueError("preset must contain 'events' object")

    tones = set(available_tones())
    mapping: dict[str, dict] = {}
    for event, actions in events.items():
        if event not in ALL_EVENTS:
            raise ValueError(f"unknown event in preset: {event!r}")
        if not isinstance(actions, dict):
            raise ValueError(f"actions of {event!r} must be an object")
        unknown = set(actions) - ALL_ACTIONS
        if unknown:
            raise ValueError(f"unknown actions for {event!r}: {sorted(unknown)}")

        norm: dict = {}
        toast = actions.get("toast")
        if toast is not None:
            if not isinstance(toast, dict) or not toast.get("text"):
                raise ValueError(f"toast of {event!r} needs 'text'")
            variant = toast.get("variant", "info")
            if variant not in _TOAST_VARIANTS:
                raise ValueError(f"bad toast variant for {event!r}: {variant!r}")
            norm["toast"] = {"variant": variant, "text": str(toast["text"])}

        sound = actions.get("sound")
        if sound is not None:
            if sound not in tones:
                raise ValueError(f"unknown tone for {event!r}: {sound!r}")
            norm["sound"] = sound

        pulse = actions.get("accent_pulse")
        if pulse is not None:
            if not isinstance(pulse, dict) or not pulse.get("color"):
                raise ValueError(f"accent_pulse of {event!r} needs 'color'")
            norm["accent_pulse"] = {
                "color": str(pulse["color"]),
                "duration_ms": int(pulse.get("duration_ms", 800)),
            }
        if norm:
            mapping[event] = norm
    return mapping


def load_preset(path: str | None = None) -> dict:
    """Загружает пресет с диска → mapping event→actions (валидированный)."""
    path = path or DEFAULT_PRESET_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return validate_preset(data)


def merge_presets(base: dict, override_path: str) -> dict:
    """Пользовательский пресет поверх базового (по событиям)."""
    override = load_preset(override_path)
    merged = {k: dict(v) for k, v in base.items()}
    merged.update(override)
    return merged
