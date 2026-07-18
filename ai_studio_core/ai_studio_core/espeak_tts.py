# -*- coding: utf-8 -*-
"""ai_studio_core/espeak_tts.py — реальный TTS-бэкенд через espeak/espeak-ng.

Используется контроллером TTS как основной локальный синтезатор в сборках
без Coqui XTTS (torch/TTS). Синтезирует настоящий WAV (16-bit mono, 22050 Hz)
через системный бинарник — без заглушек и «демо-файлов».

Если бинарник не найден — available() == False, и вызывающий код обязан
честно сообщить пользователю (а не подсовывать подделку).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass

BASE_WPM = 175          # скорость речи espeak по умолчанию
CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


@dataclass
class SynthesisResult:
    path: str
    duration_sec: float
    sample_rate: int
    frames: int


def find_espeak() -> str | None:
    """Возвращает путь к espeak-ng/espeak или None."""
    for name in ("espeak-ng", "espeak"):
        path = shutil.which(name)
        if path:
            return path
    return None


def available() -> bool:
    return find_espeak() is not None


def detect_language(text: str, default: str = "en") -> str:
    """Грубое определение языка текста: кириллица → ru, иначе default."""
    return "ru" if CYRILLIC_RE.search(text or "") else default


def resolve_voice(text: str, language: str = "auto") -> str:
    """'auto' → автоопределение по тексту, иначе код языка как есть."""
    if not language or language == "auto":
        return detect_language(text)
    return language


def wpm_from_speed(speed: float) -> int:
    """Коэффициент скорости UI (0.5–2.0) → слов в минуту espeak (80–450, clamp)."""
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 1.0
    wpm = int(round(BASE_WPM * speed))
    return max(80, min(450, wpm))


def wav_info(path: str) -> tuple[int, int, float]:
    """(frames, sample_rate, duration_sec) для WAV-файла."""
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    duration = frames / float(rate) if rate else 0.0
    return frames, rate, duration


def synthesize(
    text: str,
    out_path: str | None = None,
    *,
    language: str = "auto",
    speed: float = 1.0,
    timeout: int = 120,
    _binary: str | None = None,
) -> SynthesisResult:
    """Синтезирует речь в WAV-файл и возвращает факты о нём.

    Кидает RuntimeError при отказе бэкенда — вызывающий код показывает
    ошибку пользователю; файла-пустышки не создаётся.
    """
    binary = _binary or find_espeak()
    if not binary:
        raise RuntimeError("espeak binary not found")

    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")

    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="espeak_")
        os.close(fd)

    voice = resolve_voice(text, language)
    cmd = [
        binary,
        "-v", voice,
        "-s", str(wpm_from_speed(speed)),
        "-w", out_path,
        text,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False,
    )
    # espeak пишет предупреждения в stderr даже при успехе — судим по файлу
    if proc.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) <= 44:
        raise RuntimeError(
            f"espeak failed (code {proc.returncode}): {proc.stderr.strip()[:300]}"
        )

    frames, rate, duration = wav_info(out_path)
    if frames <= 0:
        raise RuntimeError("espeak produced zero-length audio")
    return SynthesisResult(path=out_path, duration_sec=duration, sample_rate=rate, frames=frames)
