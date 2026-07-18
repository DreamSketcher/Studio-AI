"""Pipeline Workspace — визуальный конструктор пайплайнов (каркас)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS
from .base_workspace import BaseWorkspace


class PipelineNode(QFrame):
    """Карточка-узел пайплайна на канвасе."""
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 80)
        self.setStyleSheet(
            f"background: {TOKENS.colors.bg_elevated}; "
            f"border: 2px solid {color}; "
            f"border-radius: {TOKENS.radius.md}px;"
        )
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {color}; font-weight: 600; border: none;")
        l.addWidget(lbl)


class PipelineWorkspace(BaseWorkspace):
    """Визуальный редактор нод-обработки (пока плейсхолдер)."""

    def workspace_id(self) -> str:
        return "pipeline"

    def _pipeline_steps(self) -> list[str]:
        return ["Input", "Process", "Output"]

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )
        add_in = QToolButton()
        add_in.setText("+ Input")
        add_proc = QToolButton()
        add_proc.setText("+ Processor")
        add_out = QToolButton()
        add_out.setText("+ Output")
        run = QToolButton()
        run.setText("▶ Run pipeline")
        run.setProperty("accent", True)
        run.setStyleSheet(
            f"QToolButton {{ background: {TOKENS.colors.accent_primary}; color: #fff; "
            f"border: none; font-weight: 600; padding: 8px 18px; border-radius: {TOKENS.radius.md}px; }}"
            f"QToolButton:hover {{ background: #6d28d9; }}"
        )
        for b in (add_in, add_proc, add_out):
            tb.addWidget(b)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(run)
        return tb

    def _build_canvas(self) -> QWidget:
        canvas = QWidget()
        canvas.setStyleSheet(f"background: {TOKENS.colors.bg_primary};")
        outer = QVBoxLayout(canvas)
        outer.setContentsMargins(TOKENS.spacing.xl, TOKENS.spacing.xl,
                                 TOKENS.spacing.xl, TOKENS.spacing.xl)

        hint = QLabel("Визуальный редактор пайплайнов")
        hint.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.subtitle}px; border: none;"
        )
        outer.addWidget(hint)
        sub = QLabel(
            "Собирайте цепочки обработки из нод: Input → Normalize → TTS → RVC → Output."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {TOKENS.colors.text_disabled}; border: none;")
        outer.addWidget(sub)
        outer.addSpacing(TOKENS.spacing.xl)

        # Демо-ряд нод
        grid = QHBoxLayout()
        grid.setSpacing(TOKENS.spacing.lg)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        nodes = [
            ("Input", TOKENS.colors.accent_secondary),
            ("Normalize", TOKENS.colors.accent_primary),
            ("TTS", TOKENS.colors.accent_primary),
            ("RVC", TOKENS.colors.accent_warning),
            ("De-ess", TOKENS.colors.accent_success),
            ("Output", TOKENS.colors.accent_error),
        ]
        for i, (title, color) in enumerate(nodes):
            grid.addWidget(PipelineNode(title, color))
            if i < len(nodes) - 1:
                arrow = QLabel("──→")
                arrow.setStyleSheet(
                    f"color: {TOKENS.colors.pipeline_connector}; "
                    f"font-size: 20px; border: none;"
                )
                grid.addWidget(arrow)
        outer.addLayout(grid)
        outer.addStretch(1)
        return canvas
