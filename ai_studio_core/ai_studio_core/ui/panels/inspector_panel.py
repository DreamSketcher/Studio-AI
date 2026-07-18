"""Inspector — панель свойств выбранного элемента (правый dock, tabified с Settings).

По blueprint UI-слоя панель показывает детали текущего выделения
(модель в Model Hub, задача в Queue, нода в Pipeline и т.д.).
Подключение к сигналам выбора — отдельным этапом; сейчас каркас
с явным публичным API для будущей интеграции.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class InspectorPanel(QWidget):
    """Инспектор выбранного элемента: заголовок, свойства, метаданные."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        # Ключ-свойство строки обновляются через show_item()
        self._title = QLabel("Nothing selected")
        self._title.setStyleSheet(
            f"color: {TOKENS.colors.text_primary}; "
            f"font-size: {TOKENS.font_size.subtitle}px; font-weight: 600;"
        )
        layout.addWidget(self._title)

        self._type = QLabel("")
        self._type.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; "
            f"text-transform: uppercase; letter-spacing: 1px;"
        )
        layout.addWidget(self._type)

        self._props = QWidget()
        self._props_form = QFormLayout(self._props)
        self._props_form.setContentsMargins(0, TOKENS.spacing.sm, 0, 0)
        self._props_form.setSpacing(TOKENS.spacing.xs)
        layout.addWidget(self._props)

        self._details = QPlainTextEdit()
        self._details.setReadOnly(True)
        self._details.setPlaceholderText("Details / metadata…")
        layout.addWidget(self._details, stretch=1)

    # ── Public API (будущая интеграция) ──

    def show_item(
        self,
        title: str,
        item_type: str = "",
        properties: dict | None = None,
        details: str = "",
    ) -> None:
        """Отобразить выбранный элемент: заголовок, тип, таблицу свойств."""
        self._title.setText(title)
        self._type.setText(item_type)

        while self._props_form.rowCount():
            self._props_form.removeRow(0)
        for key, value in (properties or {}).items():
            key_lbl = QLabel(f"{key}:")
            key_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary};")
            val_lbl = QLabel(str(value))
            val_lbl.setStyleSheet(f"color: {TOKENS.colors.text_primary};")
            val_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self._props_form.addRow(key_lbl, val_lbl)
        self._props.setVisible(bool(properties))

        self._details.setPlainText(details)

    def clear(self) -> None:
        self.show_item("Nothing selected")
