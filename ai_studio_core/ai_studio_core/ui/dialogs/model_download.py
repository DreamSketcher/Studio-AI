"""Model download dialog (каркас)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout,
)

from ..theme.tokens import TOKENS


class ModelDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Model")
        self.setMinimumWidth(420)

        l = QVBoxLayout(self)
        l.setSpacing(TOKENS.spacing.md)

        intro = QLabel("Выберите модель для загрузки:")
        l.addWidget(intro)

        form = QFormLayout()
        self._category = QComboBox()
        self._category.addItems(["TTS", "LLM", "RVC"])
        self._model = QComboBox()
        self._model.setEditable(True)
        self._model.addItems(["XTTS v2.0.2", "Llama 3.1 8B Q4", "RVC Male v2"])
        form.addRow("Category:", self._category)
        form.addRow("Model:", self._model)
        l.addLayout(form)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        l.addWidget(self._progress)

        btn_row = QVBoxLayout
        from PySide6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_download = QPushButton("Download")
        self._btn_download.setProperty("accent", True)
        self._btn_download.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_download)
        l.addLayout(btn_row)
