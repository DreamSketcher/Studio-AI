# -*- coding: utf-8 -*-
"""Тесты виджета волны: реальные пики из WAV + обновление транспорта."""
from __future__ import annotations

import math
import os
import struct
import wave

import pytest

from ai_studio_core import espeak_tts
from ai_studio_core.ui.widgets.waveform_view import (
    compute_peaks, wav_duration, _fmt_time,
)


def _write_sine_wav(path: str, freq: float = 440.0, seconds: float = 1.0,
                    rate: int = 22050) -> None:
    n = int(rate * seconds)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(n)
        )
        wf.writeframes(frames)


class TestComputePeaks:
    def test_sine_peaks_uniform(self, tmp_path):
        p = str(tmp_path / "sine.wav")
        _write_sine_wav(p)
        peaks = compute_peaks(p, buckets=100)
        assert len(peaks) == 100
        assert all(0.0 <= x <= 1.0 for x in peaks)
        # синус стабилен: почти все корзины близки к 1
        assert min(peaks) > 0.8
        assert max(peaks) == pytest.approx(1.0)

    def test_peaks_shape_follows_amplitude(self, tmp_path):
        """Первая половина тихая, вторая громкая — пики это отражают."""
        p = str(tmp_path / "step.wav")
        rate = 22050
        n = rate  # 1 секунда
        frames = bytearray()
        for i in range(n):
            amp = 1000 if i < n // 2 else 30000
            frames += struct.pack("<h", int(amp * math.sin(2 * math.pi * 440 * i / rate)))
        with wave.open(p, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
            wf.writeframes(bytes(frames))
        peaks = compute_peaks(p, buckets=20)
        assert max(peaks[:10]) < 0.1          # тихая половина
        assert peaks[-1] > 0.9                # громкая — у потолка

    def test_zero_length_rejected(self, tmp_path):
        p = str(tmp_path / "empty.wav")
        with wave.open(p, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(b"")
        with pytest.raises(ValueError):
            compute_peaks(p)

    def test_real_speech_peaks(self, tmp_path):
        if not espeak_tts.available():
            pytest.skip("espeak не установлен")
        out = str(tmp_path / "speech.wav")
        espeak_tts.synthesize("Waveform peaks test sentence.", out_path=out)
        peaks = compute_peaks(out)
        assert len(peaks) == 160
        assert max(peaks) == pytest.approx(1.0)
        assert any(p < 0.5 for p in peaks)  # в речи есть паузы/тишина


class TestDuration:
    def test_wav_duration(self, tmp_path):
        p = str(tmp_path / "d.wav")
        _write_sine_wav(p, seconds=2.0)
        assert wav_duration(p) == pytest.approx(2.0, abs=0.02)

    def test_fmt_time(self):
        assert _fmt_time(0) == "00:00"
        assert _fmt_time(61.4) == "01:01"
        assert _fmt_time(3600) == "60:00"


class TestWaveformWidgetOffscreen:
    @pytest.fixture(scope="class")
    def app(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication
        application = QApplication.instance() or QApplication([])
        yield application

    def test_set_audio_updates_view(self, app, tmp_path):
        from ai_studio_core.ui.widgets.waveform_view import WaveformView
        p = str(tmp_path / "sine.wav")
        _write_sine_wav(p, seconds=3.0)
        w = WaveformView()
        peaks = w.set_audio(p)
        assert len(peaks) == 160
        assert w.current_path() == p
        assert w.has_audio()
        assert w._time_total.text() == "00:03"
        assert w._canvas.peaks() == peaks

    def test_play_button_disabled_without_backend_or_player(self, app, tmp_path):
        """В offscreen-среде мультимедиа-бэкенда может не быть — тогда кнопка
        честно отключена; файл тем не менее проигрываем там, где бэкенд есть."""
        from ai_studio_core.ui.widgets.waveform_view import WaveformView
        p = str(tmp_path / "sine.wav")
        _write_sine_wav(p)
        w = WaveformView()
        w.set_audio(p)
        if w._player is None:
            assert not w._btn_play.isEnabled()
        else:
            assert w._btn_play.isEnabled()
