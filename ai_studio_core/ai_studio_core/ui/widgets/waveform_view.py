"""Визуализация аудио-волны (placeholder до полноценного QPainter-рендера)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class WaveformView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(80)
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

        wave_label = QLabel("▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁")
        wave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wave_label.setStyleSheet(
            f"color: {TOKENS.colors.waveform_cold}; "
            f"font-size: 24px; letter-spacing: 2px; border: none;"
        )
        layout.addWidget(wave_label)

        transport = QHBoxLayout()
        self._btn_play = QLabel("▶")
        self._btn_play.setFixedWidth(30)
        self._btn_play.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none; font-size: 16px;")
        transport.addWidget(self._btn_play)

        self._time_current = QLabel("00:00")
        self._time_current.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        transport.addWidget(self._time_current)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        transport.addWidget(self._seek_slider, stretch=1)

        self._time_total = QLabel("00:00")
        self._time_total.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        transport.addWidget(self._time_total)

        self._volume = QLabel("🔊")
        self._volume.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        transport.addWidget(self._volume)

        layout.addLayout(transport)

    def set_duration(self, seconds: float) -> None:
        self._time_total.setText(self._fmt(seconds))

    def set_position(self, seconds: float) -> None:
        self._time_current.setText(self._fmt(seconds))

    @staticmethod
    def _fmt(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 60:02d}:{s % 60:02d}"
