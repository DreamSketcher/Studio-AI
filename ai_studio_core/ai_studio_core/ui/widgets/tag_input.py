"""Поле ввода тегов (для промптов и т.п.) — простая реализация."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class TagInput(QWidget):
    tags_changed = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        placeholder: str = "add tag…",
    ):
        super().__init__(parent)
        self._tags: list[str] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(TOKENS.spacing.sm)

        self._tags_container = QWidget()
        self._tags_layout = QHBoxLayout(self._tags_container)
        self._tags_layout.setContentsMargins(4, 4, 4, 4)
        self._tags_layout.setSpacing(4)
        self._tags_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(self._tags_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(40)
        scroll.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border: 1px solid {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.md}px;"
        )
        root.addWidget(scroll, 1)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setFixedWidth(120)
        self._input.returnPressed.connect(self._add_from_input)
        root.addWidget(self._input)

    def _add_from_input(self) -> None:
        text = self._input.text().strip()
        if text and text not in self._tags:
            self.add_tag(text)
        self._input.clear()

    def add_tag(self, tag: str) -> None:
        tag = tag.strip()
        if not tag or tag in self._tags:
            return
        self._tags.append(tag)

        tag_w = QWidget()
        tag_w.setStyleSheet(
            f"background: {TOKENS.colors.bg_elevated}; "
            f"border: 1px solid {TOKENS.colors.border_focus}; "
            f"border-radius: {TOKENS.radius.sm}px; padding: 2px;"
        )
        tl = QHBoxLayout(tag_w)
        tl.setContentsMargins(8, 2, 2, 2)
        lbl = QLabel(tag)
        lbl.setStyleSheet(f"color: {TOKENS.colors.text_primary}; border: none; font-size: 12px;")
        btn = QPushButton("×")
        btn.setFixedSize(20, 20)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {TOKENS.colors.text_secondary}; font-weight: bold; padding: 0; }}"
            f"QPushButton:hover {{ color: {TOKENS.colors.accent_error}; }}"
        )
        btn.clicked.connect(lambda: self._remove_tag(tag, tag_w))
        tl.addWidget(lbl)
        tl.addWidget(btn)

        # Вставляем перед стретчем
        self._tags_layout.insertWidget(self._tags_layout.count() - 1, tag_w)
        self.tags_changed.emit(self._tags.copy())

    def _remove_tag(self, tag: str, widget: QWidget) -> None:
        if tag in self._tags:
            self._tags.remove(tag)
        widget.deleteLater()
        self.tags_changed.emit(self._tags.copy())

    def tags(self) -> list[str]:
        return self._tags.copy()

    def set_tags(self, tags: list[str]) -> None:
        for t in list(self._tags):
            self._remove_tag(t, self._tags_container.findChild(QWidget))
        self._tags.clear()
        for t in tags:
            self.add_tag(t)
