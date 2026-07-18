"""Сворачиваемая группа настроек — стандарт для боковых панелей."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS


class CollapsibleGroup(QWidget):
    def __init__(self, title: str, expanded: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header (clickable)
        self._header = QWidget()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border-radius: {TOKENS.radius.sm}px; "
            f"padding: {TOKENS.spacing.sm}px {TOKENS.spacing.md}px;"
        )
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self._arrow = QLabel("▼" if expanded else "▶")
        self._arrow.setFixedWidth(16)
        self._arrow.setStyleSheet(f"color: {TOKENS.colors.text_secondary};")
        header_layout.addWidget(self._arrow)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; "
            f"font-weight: 600; text-transform: uppercase; letter-spacing: 1px; "
            f"border: none;"
        )
        self._title_label = title_label
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self._header.mousePressEvent = lambda _e: self.toggle()
        layout.addWidget(self._header)

        # Content
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )
        self._content.setVisible(expanded)
        layout.addWidget(self._content)

    def set_content_layout(self, content_layout: QLayout) -> None:
        # Очищаем предыдущий layout
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # Рекурсивно убираем
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().setParent(None)
        wrapper = QWidget()
        wrapper.setLayout(content_layout)
        self._content_layout.addWidget(wrapper)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._arrow.setText("▼" if self._expanded else "▶")
        self._content.setVisible(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def title(self) -> str:
        return self._title_label.text()

    def content_widget(self) -> QWidget:
        return self._content
