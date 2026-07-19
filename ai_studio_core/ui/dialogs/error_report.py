"""Error report dialog."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from ..theme.tokens import TOKENS


class ErrorReportDialog(QDialog):
    def __init__(self, error_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Error")
        self.setMinimumSize(520, 380)

        l = QVBoxLayout(self)
        l.addWidget(QLabel("Произошла ошибка. Отправьте отчет разработчикам:"))
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlainText(error_text)
        l.addWidget(self._output, stretch=1)

        btns = QHBoxLayout()
        btns.addStretch()
        copy = QPushButton("📋 Copy")
        copy.clicked.connect(self._copy)
        close = QPushButton("Close")
        close.setProperty("accent", True)
        close.clicked.connect(self.accept)
        btns.addWidget(copy)
        btns.addWidget(close)
        l.addLayout(btns)

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._output.toPlainText())
