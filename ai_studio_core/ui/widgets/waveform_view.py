"""Визуализация аудио-волны.

set_audio(path) загружает WAV, вычисляет реальные пики амплитуды и рисует их
QPainter'ом. Проигрывание — через QSoundEffect, если мультимедиа-бэкенд
доступен (offscreen/headless — кнопка честно отключена).
"""
from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


def compute_peaks(path: str, buckets: int = 160) -> list[float]:
    """Читает WAV и возвращает список пиков амплитуды [0..1] длиной buckets.

    Работает с 8/16/24/32-bit PCM и float WAV; моно/стерео сводится.
    При невозможности разобрать файл бросает ValueError.
    """
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        framerate = wf.getframerate()
        comptype = wf.getcomptype()
        if comptype != "NONE":
            raise ValueError(f"compressed WAV not supported: {comptype}")
        raw = wf.readframes(n_frames)

    if n_frames <= 0:
        raise ValueError("zero-length wav")

    if sampwidth == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128.0) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 3:
        a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        data = (a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16))
        data = np.where(data >= 1 << 23, data - (1 << 24), data).astype(np.float32)
        data = data / float(1 << 23)
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / float(1 << 31)
        data = data.astype(np.float32)
    else:
        raise ValueError(f"unsupported sample width: {sampwidth}")

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)

    data = np.abs(data)
    if data.size == 0:
        raise ValueError("no samples")

    # Разбиваем на корзины и берём максимум в каждой
    idx = np.linspace(0, data.size, num=buckets + 1).astype(int)
    peaks = [float(data[idx[i]:idx[i + 1]].max()) if idx[i] < idx[i + 1] else 0.0
             for i in range(buckets)]
    top = max(peaks) or 1.0
    return [p / top for p in peaks]


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate() or 1)


def _fmt_time(sec: float) -> str:
    sec = max(0, int(round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


class WaveformCanvas(QWidget):
    """QPainter-канвас с барами громкости."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._peaks: list[float] = []
        self.setMinimumHeight(60)

    def set_peaks(self, peaks: list[float]) -> None:
        self._peaks = list(peaks)
        self.update()

    def peaks(self) -> list[float]:
        return list(self._peaks)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(TOKENS.colors.bg_primary))

        if not self._peaks:
            painter.setPen(QColor(TOKENS.colors.text_disabled))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            painter.end()
            return

        n = len(self._peaks)
        w = max(1, self.width())
        h = self.height()
        mid = h // 2
        bar_w = w / n

        cold = QColor(TOKENS.colors.waveform_cold)
        hot = QColor(TOKENS.colors.waveform_hot)
        pen = QPen()
        for i, p in enumerate(self._peaks):
            t = p
            color = QColor(
                int(cold.red() + (hot.red() - cold.red()) * t),
                int(cold.green() + (hot.green() - cold.green()) * t),
                int(cold.blue() + (hot.blue() - cold.blue()) * t),
            )
            pen.setColor(color)
            pen.setWidthF(max(1.0, bar_w * 0.7))
            painter.setPen(pen)
            x = int(i * bar_w + bar_w / 2)
            amp = max(2.0, p * (h - 6))
            painter.drawLine(x, int(mid - amp / 2), x, int(mid + amp / 2))
        painter.end()


class WaveformView(QWidget):
    """Единый виджет: канвас волны + транспорт (play/seek/время)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._path: str | None = None
        self._player = None  # QSoundEffect, если доступен мультимедиа-бэкенд

        self.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border: 1px solid {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.md}px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS.spacing.md, TOKENS.spacing.sm,
            TOKENS.spacing.md, TOKENS.spacing.sm,
        )

        self._canvas = WaveformCanvas()
        layout.addWidget(self._canvas, stretch=1)

        transport = QHBoxLayout()
        self._btn_play = QToolButton()
        self._btn_play.setText("▶")
        self._btn_play.setFixedWidth(36)
        self._btn_play.clicked.connect(self._toggle_play)
        transport.addWidget(self._btn_play)

        self._time_current = QLabel("00:00")
        self._time_current.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        transport.addWidget(self._time_current)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 1000)
        transport.addWidget(self._seek, stretch=1)

        self._time_total = QLabel("00:00")
        self._time_total.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        transport.addWidget(self._time_total)

        layout.addLayout(transport)

    # ── Public ──

    def set_audio(self, path: str) -> list[float]:
        """Загружает WAV: рисует пики, обновляет длительность. Возвращает пики."""
        peaks = compute_peaks(path)
        self._path = path
        self._canvas.set_peaks(peaks)
        duration = wav_duration(path)
        self._time_total.setText(_fmt_time(duration))
        self._time_current.setText("00:00")
        self._seek.setValue(0)
        self._prepare_player(path)
        return peaks

    def current_path(self) -> str | None:
        return self._path

    def has_audio(self) -> bool:
        return self._path is not None

    # ── Playback (best-effort, честно отключается без мультимедиа-бэкенда) ──

    def _prepare_player(self, path: str) -> None:
        self._player = None
        try:
            from PySide6.QtMultimedia import QSoundEffect
            from PySide6.QtCore import QUrl
            eff = QSoundEffect(self)
            eff.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            eff.setVolume(0.9)
            self._player = eff
            self._btn_play.setEnabled(True)
        except Exception:
            self._btn_play.setEnabled(False)  # нет бэкенда — честно, без подделки

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.isPlaying():
            self._player.stop()
            self._btn_play.setText("▶")
        else:
            self._player.play()
            self._btn_play.setText("⏹")
