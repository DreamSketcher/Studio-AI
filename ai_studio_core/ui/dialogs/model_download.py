"""Диалог скачивания RVC-моделей из живого каталога (rvc_catalog).

Список — реальные записи каталога (disk-кэш/seed + сеть через
sources.get_catalog()). «Скачать» запускает ModelController.download_entry —
настоящее HTTP-скачивание в models/rvc/ с прогрессом. Офлайн-каталог пуст —
честная подпись вместо манекенов.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QVBoxLayout,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS


class ModelDownloadDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self.setWindowTitle(tr("dlg_download_title"))
        self.setMinimumWidth(480)

        l = QVBoxLayout(self)
        l.setSpacing(TOKENS.spacing.md)

        self._list = QListWidget()
        entries = self._ctrl.catalog() if self._ctrl else []
        self._entries: list[dict] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            if self._ctrl.is_downloaded(e):
                continue  # уже на диске — показывать нечего
            self._entries.append(e)
            item = QListWidgetItem(f'📥  {e.get("name", e.get("id", "?"))}')
            item.setData(Qt.ItemDataRole.UserRole, e)
            self._list.addItem(item)
        if not self._entries:
            item = QListWidgetItem(tr("dlg_catalog_empty"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
        l.addWidget(self._list, stretch=1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        l.addWidget(self._progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton(tr("dlg_cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_download = QPushButton(tr("hub_download"))
        self._btn_download.setProperty("accent", True)
        self._btn_download.clicked.connect(self._on_download)
        self._btn_download.setEnabled(bool(self._entries))
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_download)
        l.addLayout(btn_row)

        if self._ctrl:
            self._ctrl.download_progress.connect(self._on_progress)
            self._ctrl.download_finished.connect(self._on_finished)
            self._ctrl.download_failed.connect(self._on_failed)

    def _selected_entry(self) -> dict | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_download(self) -> None:
        entry = self._selected_entry()
        if not entry or not self._ctrl:
            return
        self._btn_download.setEnabled(False)
        self._ctrl.download_entry(entry)

    def _on_progress(self, _name: str, pct: int) -> None:
        self._progress.setValue(int(pct))

    def _on_finished(self, _name: str) -> None:
        self._progress.setValue(100)
        self.accept()

    def _on_failed(self, _name: str, message: str) -> None:
        self._progress.setValue(0)
        self._btn_download.setEnabled(True)
        self.setWindowTitle(f'{tr("hub_download_fail")}: {message[:80]}')
