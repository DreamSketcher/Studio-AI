# -*- coding: utf-8 -*-
"""Тесты реального espeak-бэкенда TTS (ai_studio_core.espeak_tts).

Бэкенд синтезирует настоящий WAV через системный espeak-ng/espeak —
в среде CI бинарник установлен, поэтому тесты проверяют реальный звук,
а не заглушки. Если бинарника нет — поведение честного отказа проверяется
через monkeypatch.
"""
from __future__ import annotations

import os

import pytest

from ai_studio_core import espeak_tts
from ai_studio_core.espeak_tts import (
    BASE_WPM, available, detect_language, find_espeak,
    resolve_voice, synthesize, wav_info, wpm_from_speed,
)

pytestmark = pytest.mark.skipif(
    not available(), reason="espeak-ng/espeak не установлен в системе"
)


class TestDiscovery:
    def test_binary_found(self):
        path = find_espeak()
        assert path and os.path.exists(path)

    def test_available_true(self):
        assert available() is True


class TestVoiceResolution:
    def test_detect_language_cyrillic(self):
        assert detect_language("Привет, мир") == "ru"

    def test_detect_language_latin(self):
        assert detect_language("Hello world") == "en"
        assert detect_language("") == "en"

    def test_resolve_voice_auto(self):
        assert resolve_voice("Привет", "auto") == "ru"
        assert resolve_voice("Hello", "auto") == "en"

    def test_resolve_voice_explicit(self):
        assert resolve_voice("Hello", "de") == "de"
        assert resolve_voice("Hello", "") == "en"   # пустой → auto→en


class TestSpeedMapping:
    def test_base_speed(self):
        assert wpm_from_speed(1.0) == BASE_WPM

    def test_speed_bounds(self):
        assert wpm_from_speed(0.1) == 80      # нижний clamp
        assert wpm_from_speed(10.0) == 450    # верхний clamp
        assert wpm_from_speed(0.5) < BASE_WPM < wpm_from_speed(2.0)

    def test_speed_garbage(self):
        assert wpm_from_speed("junk") == BASE_WPM
        assert wpm_from_speed(None) == BASE_WPM


class TestSynthesisReal:
    def test_synthesize_english(self, tmp_path):
        out = str(tmp_path / "hello.wav")
        res = synthesize("Hello world, this is a test.", out_path=out, language="en")
        assert os.path.exists(out)
        assert res.frames > 1000, "слишком мало сэмплов — похоже на пустышку"
        assert res.sample_rate == 22050
        assert res.duration_sec > 0.2
        frames, rate, dur = wav_info(out)
        assert (frames, rate) == (res.frames, res.sample_rate)
        assert abs(dur - res.duration_sec) < 0.01

    def test_synthesize_russian(self, tmp_path):
        out = str(tmp_path / "privet.wav")
        res = synthesize("Привет, мир!", out_path=out, language="auto")
        assert os.path.exists(out) and res.frames > 1000

    def test_synthesize_into_tempfile(self):
        res = synthesize("Temporary output test.", language="en")
        try:
            assert os.path.exists(res.path)
            assert res.path.endswith(".wav")
        finally:
            os.remove(res.path)

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            synthesize("   ")
        with pytest.raises(ValueError):
            synthesize("")


class TestHonestFailure:
    def test_missing_binary_raises(self, monkeypatch, tmp_path):
        """Нет бинарника → RuntimeError, а не тихая пустышка."""
        monkeypatch.setattr(espeak_tts.shutil, "which", lambda _n: None)
        monkeypatch.setattr(espeak_tts, "find_espeak", lambda: None)
        with pytest.raises(RuntimeError, match="not found"):
            synthesize("Hello", out_path=str(tmp_path / "x.wav"))
        assert not (tmp_path / "x.wav").exists()

    def test_backend_produces_real_file_not_placeholder(self, tmp_path):
        """Анти-заглушка: размер файла адекватен длительности речи."""
        out = str(tmp_path / "real.wav")
        synthesize("This sentence should take a couple of seconds to pronounce.",
                   out_path=out, language="en")
        # 22050 Hz * 16 bit * mono ≈ 44100 B/s; файл должен быть заметно больше
        assert os.path.getsize(out) > 44_100 * 0.5
