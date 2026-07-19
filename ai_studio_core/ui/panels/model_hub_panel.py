"""Model Hub — левый dock. Реальный список файлов из models/ (без манекенов)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS


def _fmt_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.2f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


class ModelHubPanel(QWidget):
    download_requested = Signal()      # открыть диалог скачивания каталога
    delete_requested = Signal(str)     # path выбранной модели
    refresh_requested = Signal()
    selection_changed = Signal(dict)   # данные выбранной модели (для Inspector)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._models: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        self._category = QComboBox()
        self._category.addItem(tr("hub_all"), userData="")
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
        layout.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        self._btn_download = QPushButton(tr("hub_download"))
        self._btn_download.clicked.connect(self.download_requested.emit)
        self._btn_delete = QPushButton(tr("hub_delete"))
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete_clicked)
        self._btn_refresh = QPushButton(tr("hub_refresh"))
        self._btn_refresh.clicked.connect(self.refresh_requested.emit)
        actions.addWidget(self._btn_download)
        actions.addWidget(self._btn_delete)
        actions.addWidget(self._btn_refresh)
        layout.addLayout(actions)

        self._search.textChanged.connect(self._apply_filter)
        self._category.currentIndexChanged.connect(lambda _i: self._apply_filter())
        self._list.currentItemChanged.connect(self._on_current_changed)

    # ── Данные ──

    def set_models(self, models: list[dict]) -> None:
        """Наполняет список реальным сканом models/. Пусто — честная строка."""
        self._models = list(models)
        # Пересобираем фильтр категорий из реальных данных
        cats = sorted({m.get("category", "root") for m in self._models})
        prev = self._category.currentData() or ""
        self._category.blockSignals(True)
        self._category.clear()
        self._category.addItem(tr("hub_all"), userData="")
        for c in cats:
            self._category.addItem(c, userData=c)
        idx = self._category.findData(prev)
        self._category.setCurrentIndex(idx if idx >= 0 else 0)
        self._category.blockSignals(False)
        self._apply_filter()

    def models(self) -> list[dict]:
        return list(self._models)

    def _filtered(self) -> list[dict]:
        query = self._search.text().strip().lower()
        cat = self._category.currentData() or ""
        out = []
        for m in self._models:
            if cat and m.get("category") != cat:
                continue
            if query and query not in m.get("name", "").lower():
                continue
            out.append(m)
        return out

    def _apply_filter(self) -> None:
        self._list.clear()
        filtered = self._filtered()
        if not filtered:
            item = QListWidgetItem(tr("hub_empty"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # некликабельный честный текст
            self._list.addItem(item)
            return
        for m in filtered:
            item = QListWidgetItem(
                f'✅  {m["name"]}\n     {m.get("category", "root")} · '
                f'{tr("hub_size")} {_fmt_size(m.get("size_bytes", 0))}'
            )
            item.setData(Qt.ItemDataRole.UserRole, m)
            self._list.addItem(item)

    def selected_model(self) -> dict | None:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ── События ──

    def _on_current_changed(self, current, _previous) -> None:
        model = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._btn_delete.setEnabled(model is not None)
        if model:
            self.selection_changed.emit(dict(model))

    def _on_delete_clicked(self) -> None:
        model = self.selected_model()
        if model:
            self.delete_requested.emit(model["path"])

    def retranslate_ui(self) -> None:
        self._category.setItemText(0, tr("hub_all"))
        self._search.setPlaceholderText(tr("hub_search_ph"))
        self._btn_download.setText(tr("hub_download"))
        self._btn_delete.setText(tr("hub_delete"))
        self._btn_refresh.setText(tr("hub_refresh"))
        self._apply_filter()
