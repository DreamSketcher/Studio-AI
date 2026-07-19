"""Универсальный селектор модели/провайдера.

Без демо-данных: виджет стартует пустым и наполняется только через
set_models() реальными данными контроллера — каталогом моделей активного
провайдера, списком доступных TTS-бэкендов или файлами моделей на диске.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QWidget

_STATUS_ICONS = {"ready": "✅", "download": "📥", "error": "❌", "loading": "⏳"}


class ModelSelector(QComboBox):
    model_changed = Signal(str)  # id выбранной модели (userData)

    def __init__(
        self,
        category: str = "tts",
        placeholder: str = "Select model…",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._category = category
        self.setPlaceholderText(placeholder)
        self.setMinimumWidth(220)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # Список пуст до вызова set_models() — никаких заглушек.
        self.currentTextChanged.connect(self._on_changed)

    def set_models(self, models: list[dict]) -> None:
        """Пересобирает список БЕЗ эмиссии model_changed.

        models: [{"id": str, "name": str, "provider": str,
                  "status": ready|download|error|loading, "current": bool}]
        Запись с current=True программно выбирается (тоже без сигнала).
        """
        self.blockSignals(True)
        try:
            self.clear()
            current_provider = None
            current_idx = -1
            for m in models:
                provider = m.get("provider", "")
                if provider != current_provider:
                    if current_provider is not None:
                        self.insertSeparator(self.count())
                    current_provider = provider
                icon = _STATUS_ICONS.get(m.get("status", ""), "")
                name = m.get("name", m.get("id", ""))
                if icon and provider:
                    display = f"{icon} {name}  ({provider})"
                elif icon:
                    display = f"{icon} {name}"
                else:
                    display = name
                self.addItem(display, userData=m.get("id"))
                if m.get("current"):
                    current_idx = self.count() - 1
            if current_idx >= 0:
                self.setCurrentIndex(current_idx)
            elif self.count():
                self.setCurrentIndex(0)
        finally:
            self.blockSignals(False)

    def current_model_id(self) -> str:
        """id выбранной записи (userData), '' если список пуст/id не задан."""
        data = self.currentData()
        return str(data) if data else ""

    def select_id(self, model_id: str) -> bool:
        """Программно выбирает запись по id без эмиссии model_changed."""
        idx = self.findData(model_id)
        if idx < 0:
            return False
        was = self.blockSignals(True)
        self.setCurrentIndex(idx)
        self.blockSignals(was)
        return True

    def _on_changed(self, _text: str) -> None:
        model_id = self.currentData()
        if model_id:
            self.model_changed.emit(str(model_id))
