"""Полупрозрачный оверлей с прогресс-баром и кнопкой отмены."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class ProgressOverlay(QWidget):
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget()
        card.setFixedSize(360, 160)
        card.setStyleSheet(
            f"background: {TOKENS.colors.bg_elevated}; "
            f"border: 1px solid {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.lg}px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(TOKENS.spacing.md)

        self._status_label = QLabel("Processing…")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"color: {TOKENS.colors.text_primary}; "
            f"font-size: {TOKENS.font_size.subtitle}px; "
            f"font-weight: 600; border: none;"
        )
        card_layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        card_layout.addWidget(self._progress)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setFixedWidth(100)
        self._btn_cancel.clicked.connect(self.cancel_requested.emit)
        card_layout.addWidget(self._btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(card)

    def show_progress(self, status: str = "Processing…", value: int = 0) -> None:
        self._status_label.setText(status)
        self._progress.setValue(value)
        self.setVisible(True)
        self.raise_()

    def update_progress(self, value: int, status: str | None = None) -> None:
        self._progress.setValue(value)
        if status:
            self._status_label.setText(status)

    def hide_progress(self) -> None:
        self.setVisible(False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        if self.parent():
            self.setGeometry(self.parent().rect())
