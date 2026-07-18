"""Pipeline Workspace — визуальный конструктор/запуск цепочки обработки.

Ноды соответствуют реальным этапам TTS-пайплайна; кнопка «Run» запускает
обработку введённого текста через PipelineController, состояния нод
отражают ход выполнения. Строки — через i18n.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextEdit, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS
from .base_workspace import BaseWorkspace


class PipelineNode(QFrame):
    """Карточка-узел пайплайна на канвасе."""

    def __init__(self, title: str, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._base_color = color
        self.setFixedSize(160, 80)
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl = QLabel(title)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self._lbl)
        self.set_state("idle")
        self.set_title(title)

    def set_title(self, title: str) -> None:
        self._lbl.setText(title)

    def set_state(self, state: str) -> None:
        colors = {
            "idle": self._base_color,
            "active": TOKENS.colors.accent_primary,
            "done": TOKENS.colors.accent_success,
            "error": TOKENS.colors.accent_error,
        }
        c = colors.get(state, self._base_color)
        bg = TOKENS.colors.bg_elevated if state == "idle" else {
            "active": TOKENS.colors.bg_tertiary,
            "done": "rgba(16,185,129,0.12)",
            "error": "rgba(239,68,68,0.12)",
        }.get(state, TOKENS.colors.bg_elevated)
        self.setStyleSheet(
            f"background: {bg}; border: 2px solid {c}; "
            f"border-radius: {TOKENS.radius.md}px;"
        )
        self._lbl.setStyleSheet(
            f"color: {c}; font-weight: 600; border: none; background: transparent;"
        )


class PipelineWorkspace(BaseWorkspace):
    """Визуальный редактор нод-обработки + реальный запуск цепочки."""

    run_requested = Signal(str)          # исходный текст
    stop_requested = Signal()

    NODE_COLORS = [
        TOKENS.colors.accent_secondary,   # Input
        TOKENS.colors.accent_primary,     # Normalize
        TOKENS.colors.accent_primary,     # TTS
        TOKENS.colors.accent_warning,     # RVC
        TOKENS.colors.accent_success,     # De-ess
        TOKENS.colors.accent_error,       # Output
    ]

    def workspace_id(self) -> str:
        return "pipeline"

    def _node_titles(self) -> list[str]:
        return [
            tr("step_input"), tr("step_normalize"), tr("step_tts"),
            tr("step_rvc"), tr("step_deess"), tr("step_output"),
        ]

    def _pipeline_steps(self) -> list[str]:
        return self._node_titles()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )
        self._btn_run = QToolButton()
        self._btn_run.setText(tr("pipe_run"))
        self._btn_run.setStyleSheet(
            f"QToolButton {{ background: {TOKENS.colors.accent_primary}; color: #fff; "
            f"border: none; font-weight: 600; padding: 8px 18px; "
            f"border-radius: {TOKENS.radius.md}px; }}"
            f"QToolButton:hover {{ background: #6d28d9; }}"
        )
        self._btn_run.clicked.connect(self._on_run)

        self._btn_stop = QToolButton()
        self._btn_stop.setText(tr("tts_stop"))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(self._btn_run)
        tb.addWidget(self._btn_stop)
        return tb

    def _build_canvas(self) -> QWidget:
        canvas = QWidget()
        canvas.setStyleSheet(f"background: {TOKENS.colors.bg_primary};")
        outer = QVBoxLayout(canvas)
        outer.setContentsMargins(TOKENS.spacing.xl, TOKENS.spacing.xl,
                                 TOKENS.spacing.xl, TOKENS.spacing.xl)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.subtitle}px; border: none;"
        )
        outer.addWidget(self._hint)
        self._sub = QLabel()
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet(f"color: {TOKENS.colors.text_disabled}; border: none;")
        outer.addWidget(self._sub)
        outer.addSpacing(TOKENS.spacing.md)

        # Исходный текст для запуска
        self._input_lbl = QLabel()
        self._input_lbl.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; border: none; font-weight: 600;"
        )
        outer.addWidget(self._input_lbl)
        self._input = QTextEdit()
        self._input.setMaximumHeight(110)
        outer.addWidget(self._input)
        outer.addSpacing(TOKENS.spacing.lg)

        # Ряд нод от реальных этапов пайплайна
        grid = QHBoxLayout()
        grid.setSpacing(TOKENS.spacing.lg)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._nodes: list[PipelineNode] = []
        titles = self._node_titles()
        for i, (title, color) in enumerate(zip(titles, self.NODE_COLORS)):
            node = PipelineNode(title, color)
            self._nodes.append(node)
            grid.addWidget(node)
            if i < len(titles) - 1:
                arrow = QLabel("──→")
                arrow.setStyleSheet(
                    f"color: {TOKENS.colors.pipeline_connector}; "
                    f"font-size: 20px; border: none;"
                )
                grid.addWidget(arrow)
        outer.addLayout(grid)
        outer.addStretch(1)

        self.retranslate_ui()
        return canvas

    # ── i18n ──

    def retranslate_ui(self) -> None:
        self._hint.setText(tr("pipe_title"))
        self._sub.setText(tr("pipe_hint"))
        self._input_lbl.setText(tr("pipe_input_lbl"))
        self._input.setPlaceholderText(tr("pipe_input_ph"))
        self._btn_run.setText(tr("pipe_run"))
        self._btn_stop.setText(tr("tts_stop"))
        for node, title in zip(self._nodes, self._node_titles()):
            node.set_title(title)
        if self._pipeline_strip is not None:
            self._pipeline_strip.set_steps(self._pipeline_steps())

    # ── Behavior ──

    def _on_run(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.run_requested.emit(text)

    def set_node_states(self, states: list[str]) -> None:
        for node, state in zip(self._nodes, states):
            node.set_state(state)

    def set_node_state(self, index: int, state: str) -> None:
        if 0 <= index < len(self._nodes):
            self._nodes[index].set_state(state)

    def reset_nodes(self) -> None:
        for node in self._nodes:
            node.set_state("idle")

    def set_busy(self, busy: bool) -> None:
        self._btn_run.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
