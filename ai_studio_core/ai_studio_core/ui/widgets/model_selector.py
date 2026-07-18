"""Универсальный селектор модели/провайдера."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QWidget


class ModelSelector(QComboBox):
    model_changed = Signal(str)

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

        if category == "tts":
            self.addItems(["XTTS v2.0.2", "XTTS v2.0.1", "StyleTTS2", "Bark-small"])
        elif category == "llm":
            self.addItems(["GPT-4o", "GPT-4o-mini", "Claude 3.5 Sonnet", "Groq Llama 3.1 70B", "Local: Llama 3.1 8B"])
        elif category == "rvc":
            self.addItems(["(none)", "Male v2", "Female v1", "Custom…"])
        else:
            self.addItem(placeholder)

        self.currentTextChanged.connect(self._on_changed)

    def set_models(self, models: list[dict]) -> None:
        self.clear()
        current_provider = None
        for m in models:
            provider = m.get("provider", "")
            if provider != current_provider:
                if current_provider is not None:
                    self.insertSeparator(self.count())
                current_provider = provider
            status_icon = {"ready": "✅", "download": "📥", "error": "❌", "loading": "⏳"}.get(m.get("status", ""), "")
            display = f"{status_icon} {m['name']}  ({provider})" if status_icon else m["name"]
            self.addItem(display, userData=m.get("id"))

    def _on_changed(self, text: str) -> None:
        model_id = self.currentData()
        if model_id:
            self.model_changed.emit(str(model_id))
