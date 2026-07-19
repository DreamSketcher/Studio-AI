"""About dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from ..theme.tokens import TOKENS


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About AI Studio")
        self.setMinimumWidth(420)
        l = QVBoxLayout(self)
        l.setContentsMargins(TOKENS.spacing.xl, TOKENS.spacing.xl,
                             TOKENS.spacing.xl, TOKENS.spacing.lg)
        l.setSpacing(TOKENS.spacing.md)

        title = QLabel("✨ AI Studio")
        title.setStyleSheet(f"font-size: {TOKENS.font_size.headline}px; font-weight: 700; color: {TOKENS.colors.text_primary}; border: none;")
        l.addWidget(title)

        ver = QLabel("Version 0.1.0")
        ver.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        l.addWidget(ver)

        desc = QLabel(
            "Headless AI-studio core extracted from XTTS-Studio-AI.\n"
            "TTS, RVC, LLM-chat, batch processing and environment management\n"
            "with a PySide6 front-end.\n\n"
            "Licensed under MIT."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        l.addWidget(desc)

        btn = QPushButton("OK")
        btn.setProperty("accent", True)
        btn.clicked.connect(self.accept)
        l.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
