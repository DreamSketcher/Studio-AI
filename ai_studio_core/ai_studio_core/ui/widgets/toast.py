"""Всплывающее уведомление (toast) в углу экрана."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPropertyAnimation, QTimer, Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from ..theme.tokens import TOKENS


class Toast(QWidget):
    _VARIANTS = {
        "info":    (TOKENS.colors.accent_secondary, "ℹ"),
        "success": (TOKENS.colors.accent_success,   "✓"),
        "warning": (TOKENS.colors.accent_warning,   "⚠"),
        "error":   (TOKENS.colors.accent_error,     "✕"),
    }

    def __init__(
        self,
        message: str,
        variant: str = "info",
        duration_ms: int = 3000,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        color, icon = self._VARIANTS.get(variant, self._VARIANTS["info"])

        self.setStyleSheet(
            f"background: {TOKENS.colors.bg_elevated}; "
            f"border: 1px solid {color}; "
            f"border-left: 4px solid {color}; "
            f"border-radius: {TOKENS.radius.md}px; "
            f"padding: {TOKENS.spacing.md}px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            TOKENS.spacing.md, TOKENS.spacing.sm,
            TOKENS.spacing.md, TOKENS.spacing.sm,
        )

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: bold; border: none;"
        )
        layout.addWidget(icon_label)

        text_label = QLabel(message)
        text_label.setStyleSheet(
            f"color: {TOKENS.colors.text_primary}; "
            f"font-size: {TOKENS.font_size.body}px; border: none;"
        )
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._timer.start(duration_ms)

        self.adjustSize()

    def _fade_out(self) -> None:
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(TOKENS.duration.normal)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.finished.connect(self.close)
        anim.start()

    def show_at(self, parent: QWidget) -> None:
        """Показывает toast в правом нижнем углу parent."""
        if parent is None:
            self.show()
            return
        px = parent.rect().bottomRight()
        g = parent.mapToGlobal(px)
        self.adjustSize()
        self.move(g.x() - self.width() - TOKENS.spacing.lg,
                  g.y() - self.height() - TOKENS.spacing.lg)
        self.show()
