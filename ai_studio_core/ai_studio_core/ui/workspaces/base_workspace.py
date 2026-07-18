"""Абстрактный базовый класс для всех workspace'ов."""
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from ..widgets.pipeline_strip import PipelineStrip

if TYPE_CHECKING:
    from ..controllers.base_controller import BaseController


class BaseWorkspace(QWidget):
    """
    Наследники реализуют:
        _build_toolbar()   → QToolBar
        _build_canvas()    → QWidget (центр)
        _build_sidebar()   → QWidget | None (панель параметров справа)
        _pipeline_steps()  → list[str]
        workspace_id()     → str
    """

    def __init__(self, controller: BaseController | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._pipeline_strip: PipelineStrip | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = self._build_toolbar()
        if toolbar:
            layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        canvas = self._build_canvas()
        splitter.addWidget(canvas)

        sidebar = self._build_sidebar()
        if sidebar:
            splitter.addWidget(sidebar)
            splitter.setStretchFactor(0, 7)
            splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, stretch=1)

        steps = self._pipeline_steps()
        if steps:
            self._pipeline_strip = PipelineStrip(steps)
            layout.addWidget(self._pipeline_strip)

    @abstractmethod
    def _build_toolbar(self) -> QToolBar | None: ...

    @abstractmethod
    def _build_canvas(self) -> QWidget: ...

    def _build_sidebar(self) -> QWidget | None:
        return None

    def _pipeline_steps(self) -> list[str]:
        return []

    @abstractmethod
    def workspace_id(self) -> str: ...

    def pipeline(self) -> PipelineStrip | None:
        return self._pipeline_strip
