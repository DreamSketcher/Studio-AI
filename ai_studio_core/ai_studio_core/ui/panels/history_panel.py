"""History — левый dock (tabified с Model Hub).

Показывает реальные файлы из каталога вывода (outputs/), отсортированные
по времени изменения. Никаких демо-записей.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg"}

_TYPE_ICONS = {"TTS": "🎙", "Chat": "💬", "Image": "🖼"}


def scan_outputs(output_dir: str) -> list[dict]:
    """Реальные аудиофайлы каталога: новые сверху."""
    entries: list[dict] = []
    try:
        for name in os.listdir(output_dir):
            ext = os.path.splitext(name)[1].lower()
            if ext not in AUDIO_EXTS:
                continue
            full = os.path.join(output_dir, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            entries.append({
                "path": full,
                "name": name,
                "mtime": st.st_mtime,
                "size": st.st_size,
                "type": "TTS",
            })
    except OSError:
        return []
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def _fmt_time(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%d.%m %H:%M")


class HistoryPanel(QWidget):
    item_selected = Signal(str)     # path
    item_deleted = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._entries: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        filter_row = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.addItems([tr("hist_all"), "TTS"])
        self._type_filter.setFixedWidth(90)
        self._type_filter.currentIndexChanged.connect(lambda _i: self._apply_filter())
        filter_row.addWidget(self._type_filter)
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("hist_search_ph"))
        self._search.textChanged.connect(lambda _t: self._apply_filter())
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
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self._list, stretch=1)

        self.refresh()

    # ── Public ──

    def refresh(self) -> None:
        """Перечитывает outputs-каталог (после генерации, при старте и т.д.)."""
        try:
            from ai_studio_core.paths import OUTPUT_DIR
            output_dir = OUTPUT_DIR
        except Exception:
            output_dir = "outputs"
        self._entries = scan_outputs(output_dir)
        self._apply_filter()

    def entries(self) -> list[dict]:
        return list(self._entries)

    # ── Internals ──

    def _apply_filter(self) -> None:
        self._list.clear()
        query = self._search.text().strip().lower()
        type_filter = self._type_filter.currentText()
        shown = 0
        for e in self._entries:
            if type_filter != tr("hist_all") and e["type"] != type_filter:
                continue
            if query and query not in e["name"].lower():
                continue
            icon = _TYPE_ICONS.get(e["type"], "📄")
            size_mb = e["size"] / (1024 * 1024)
            item = QListWidgetItem(
                f'{icon} {e["name"]}\n     {_fmt_time(e["mtime"])} · {size_mb:.2f} MB'
            )
            item.setData(32, e["path"])  # Qt.UserRole
            self._list.addItem(item)
            shown += 1
        if shown == 0:
            self._list.addItem(QListWidgetItem(tr("hist_empty")))

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(32)
        if path:
            self.item_selected.emit(path)

    def _on_current_changed(self, item: QListWidgetItem, _prev) -> None:
        # Одиночный выбор тоже полезен (Inspector покажет файл)
        if item is None:
            return
        path = item.data(32)
        if path:
            self.item_selected.emit(path)

    def retranslate_ui(self) -> None:
        self._type_filter.blockSignals(True)
        self._type_filter.setItemText(0, tr("hist_all"))
        self._type_filter.blockSignals(False)
        self._search.setPlaceholderText(tr("hist_search_ph"))
        self._apply_filter()
