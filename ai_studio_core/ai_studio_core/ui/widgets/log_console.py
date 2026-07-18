"""Встроенная консоль логов с цветовой подсветкой по уровням."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QPlainTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class LogConsole(QWidget):
    log_entry = Signal(str, str)  # (level, message)

    _LEVEL_COLORS = {
        "DEBUG": TOKENS.colors.text_disabled,
        "INFO":  TOKENS.colors.text_secondary,
        "WARN":  TOKENS.colors.accent_warning,
        "ERROR": TOKENS.colors.accent_error,
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.xs,
            TOKENS.spacing.sm, TOKENS.spacing.xs,
        )

        self._level_filter = QComboBox()
        self._level_filter.addItems(["ALL", "DEBUG", "INFO", "WARN", "ERROR"])
        self._level_filter.setCurrentText("INFO")
        self._level_filter.setFixedWidth(100)
        filter_bar.addWidget(self._level_filter)
        filter_bar.addStretch()

        btn_clear = QToolButton()
        btn_clear.setText("Clear")
        btn_clear.clicked.connect(self._clear)
        filter_bar.addWidget(btn_clear)

        layout.addLayout(filter_bar)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(5000)
        self._output.setStyleSheet(
            f"QPlainTextEdit {{ "
            f"background: {TOKENS.colors.bg_primary}; "
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace; "
            f"font-size: {TOKENS.font_size.caption}px; "
            f"border: none; }}"
        )
        layout.addWidget(self._output)

        self.log_entry.connect(self._append_log)

    @Slot(str, str)
    def _append_log(self, level: str, message: str) -> None:
        color = self._LEVEL_COLORS.get(level, TOKENS.colors.text_secondary)
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level:>5}] {message}"

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self._output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(line + "\n", fmt)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def append(self, level: str, message: str) -> None:
        """Публичный метод — прямой вызов (для использования из контроллеров)."""
        self._append_log(level, message)

    def info(self, message: str) -> None:
        self.append("INFO", message)

    def warn(self, message: str) -> None:
        self.append("WARN", message)

    def error(self, message: str) -> None:
        self.append("ERROR", message)

    def debug(self, message: str) -> None:
        self.append("DEBUG", message)

    def _clear(self) -> None:
        self._output.clear()
