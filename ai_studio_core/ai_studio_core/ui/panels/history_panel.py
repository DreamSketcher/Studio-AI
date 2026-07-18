"""History — левый dock (tabified с Model Hub)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class HistoryPanel(QWidget):
    item_selected = Signal(str)
    item_deleted = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        filter_row = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.addItems(["All", "TTS", "Chat", "Image"])
        self._type_filter.setFixedWidth(80)
        filter_row.addWidget(self._type_filter)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search history…")
        filter_row.addWidget(self._search)
        layout.addLayout(filter_row)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {TOKENS.colors.bg_primary}; "
            f"border: 1px solid {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.sm}px; outline: none; }}"
            f"QListWidget::item {{ padding: {TOKENS.spacing.sm}px; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; }}"
        )
        for text, time, type_ in [
            ("Hello world test…", "2 min ago", "🎙 TTS"),
            ("Write a poem about…", "15 min ago", "💬 Chat"),
            ("Long narration ch.1…", "1 hour ago", "🎙 TTS"),
            ("RVC conversion 01…", "3 hours ago", "🎙 RVC"),
        ]:
            self._list.addItem(QListWidgetItem(f"{type_}  {text}\n     {time}"))
        layout.addWidget(self._list, stretch=1)
