"""Реальные звуковые тона experience-слоя.

Никаких бинарных заглушек: каждый тон синтезируется numpy'ом в настоящий
WAV (22050 Гц, mono, 16-bit PCM) с огибающей attack/release, кэшируется в
CACHE_DIR/experience/. Детерминировано — одинаковый вход, одинаковый файл.
"""
from __future__ import annotations

import os
import wave

import numpy as np

SAMPLE_RATE = 22050
_AMPLITUDE = 0.32
_ENVELOPE_SEC = 0.012

# Ноты = (частота Гц, длительность с). Названия регистрируются здесь —
# пресет со звуком вне списка отклоняется валидатором.
TONES: dict[str, list[tuple[float, float]]] = {
    # G4→C5: мягкий старт приложения
    "start_soft": [(392.00, 0.090), (523.25, 0.120)],
    # C5→E5→G5: арпеджио завершения генерации
    "done_chime": [(523.25, 0.070), (659.25, 0.070), (783.99, 0.150)],
    # A3→F3: нисходящий сигнал ошибки
    "error_low": [(220.00, 0.150), (174.61, 0.210)],
    # E5→A5: мягкое «всё готово»
    "success_soft": [(659.25, 0.090), (880.00, 0.130)],
    # короткий тик для мелких успехов (экспорт, ответ чата)
    "tick": [(880.00, 0.045)],
}


def available_tones() -> list[str]:
    return sorted(TONES)


def tone_wav(name: str) -> np.ndarray:
    """Синтезирует тон → float32-массив сэмплов в диапазоне [-1, 1]."""
    if name not in TONES:
        raise ValueError(f"unknown tone: {name!r}")
    parts = []
    env_n = max(1, int(_ENVELOPE_SEC * SAMPLE_RATE))
    for freq, dur in TONES[name]:
        n = int(SAMPLE_RATE * dur)
        t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
        wave_ = np.sin(2.0 * np.pi * freq * t)
        env = np.ones(n, dtype=np.float32)
        k = min(env_n, n // 2)
        env[:k] = np.linspace(0.0, 1.0, k)
        env[-k:] = np.linspace(1.0, 0.0, k)
        parts.append(wave_ * env)
    return (np.concatenate(parts) * _AMPLITUDE).astype(np.float32)


def _write_wav(path: str, samples: np.ndarray) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm16 = (pcm * 32767.0).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())


def tone_path(name: str, cache_dir: str | None = None) -> str:
    """Путь к WAV-файлу тона (ленивая синтезация + кэш на диске)."""
    if cache_dir is None:
        from ai_studio_core.paths import CACHE_DIR
        cache_dir = CACHE_DIR
    out_dir = os.path.join(cache_dir, "experience")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.wav")
    if not os.path.isfile(path):
        _write_wav(path, tone_wav(name))
    return path
