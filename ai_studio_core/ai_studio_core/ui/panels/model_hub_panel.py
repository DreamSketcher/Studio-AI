"""Model Hub — левый dock."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class ModelHubPanel(QWidget):
    download_requested = Signal(str)
    delete_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        self._category = QComboBox()
        self._category.addItems(["All", "TTS", "LLM", "RVC", "Image"])
        layout.addWidget(self._category)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Search models…")
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {TOKENS.colors.bg_primary}; "
            f"border: 1px solid {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.sm}px; outline: none; }}"
            f"QListWidget::item {{ padding: {TOKENS.spacing.sm}px; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; }}"
            f"QListWidget::item:selected {{ background: {TOKENS.colors.bg_tertiary}; color: #fff; }}"
        )
        for name, status, size in [
            ("XTTS v2.0.2", "✅ Ready", "1.8 GB"),
            ("RVC Male v2", "✅ Ready", "420 MB"),
            ("GPT-4o", "☁️ API", "—"),
            ("Claude 3.5", "☁️ API", "—"),
            ("Llama 3.1 8B Q4", "📥 Download", "4.7 GB"),
        ]:
            self._list.addItem(QListWidgetItem(f"{status}  {name}\n     Size: {size}"))
        layout.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        btn_download = QPushButton("📥 Download")
        btn_download.clicked.connect(lambda: self.download_requested.emit("selected_model"))
        btn_delete = QPushButton("🗑 Delete")
        btn_delete.clicked.connect(lambda: self.delete_requested.emit("selected_model"))
        actions.addWidget(btn_download)
        actions.addWidget(btn_delete)
        layout.addLayout(actions)
