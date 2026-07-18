"""Model Hub — левый dock."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS


class ModelHubPanel(QWidget):
    download_requested = Signal(str)
    delete_requested = Signal(str)
    refresh_requested = Signal()
    selection_changed = Signal(dict)     # данные выбранной модели (для Inspector)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        self._category = QComboBox()
        self._category.addItems([tr("hub_all"), "TTS", "LLM", "RVC", "Image"])
        layout.addWidget(self._category)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("hub_search_ph"))
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
            self._list.addItem(QListWidgetItem(f'{status}  {name}\n     {tr("hub_size")} {size}'))
        layout.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        self._btn_download = QPushButton(tr("hub_download"))
        self._btn_download.clicked.connect(lambda: self.download_requested.emit("selected_model"))
        self._btn_delete = QPushButton(tr("hub_delete"))
        self._btn_delete.clicked.connect(lambda: self.delete_requested.emit("selected_model"))
        actions.addWidget(self._btn_download)
        actions.addWidget(self._btn_delete)
        layout.addLayout(actions)

    def retranslate_ui(self) -> None:
        self._category.setItemText(0, tr("hub_all"))
        self._search.setPlaceholderText(tr("hub_search_ph"))
        self._btn_download.setText(tr("hub_download"))
        self._btn_delete.setText(tr("hub_delete"))
