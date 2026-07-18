"""Зона drag-and-drop для файлов с визуальной обратной связью."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

from ..theme.tokens import TOKENS


class FileDropZone(QWidget):
    file_dropped = Signal(str)  # path

    def __init__(
        self,
        accepted_extensions: list[str] | None = None,
        label: str = "Drop file here\nor click to browse",
        max_height: int = 120,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._accepted = [e.lower() for e in (accepted_extensions or [])]
        self._current_path: str | None = None

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMaximumHeight(max_height)
        self.setMinimumHeight(80)

        self._base_style = (
            f"border: 2px dashed {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.lg}px; "
            f"background: {TOKENS.colors.bg_secondary};"
        )
        self._hover_style = (
            f"border: 2px dashed {TOKENS.colors.accent_primary}; "
            f"border-radius: {TOKENS.radius.lg}px; "
            f"background: {TOKENS.colors.bg_tertiary};"
        )
        self.setStyleSheet(self._base_style)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.body}px; "
            f"border: none;"
        )
        layout.addWidget(self._label)

    def current_path(self) -> str | None:
        return self._current_path

    def clear(self) -> None:
        self._current_path = None
        self._label.setText("Drop file here\nor click to browse")
        self._label.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.body}px; "
            f"border: none;"
        )

    # ── Drag & Drop ──
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._hover_style)

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._base_style)

    def dropEvent(self, event) -> None:
        self.setStyleSheet(self._base_style)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if self._is_accepted(path):
                self._set_file(path)
                event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            ext_filter = " ".join(f"*{e}" for e in self._accepted) if self._accepted else "All files (*.*)"
            path, _ = QFileDialog.getOpenFileName(
                self, "Select File", "", f"Accepted ({ext_filter})"
            )
            if path:
                self._set_file(path)

    def _is_accepted(self, path: str) -> bool:
        if not self._accepted:
            return True
        return Path(path).suffix.lower() in self._accepted

    def _set_file(self, path: str) -> None:
        self._current_path = path
        name = Path(path).name
        self._label.setText(f"📎 {name}")
        self._label.setStyleSheet(
            f"color: {TOKENS.colors.text_primary}; "
            f"font-size: {TOKENS.font_size.body}px; "
            f"font-weight: 500; border: none;"
        )
        self.file_dropped.emit(path)
