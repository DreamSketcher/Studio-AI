"""Горизонтальная визуализация пайплайна обработки."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..theme.tokens import TOKENS


class PipelineStrip(QWidget):
    """
    Состояния этапа:
        "idle"   — серый
        "active" — фиолетовый
        "done"   — зелёный
        "error"  — красный
    """

    def __init__(self, steps: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border-top: 1px solid {TOKENS.colors.border_default};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            TOKENS.spacing.lg, TOKENS.spacing.xs,
            TOKENS.spacing.lg, TOKENS.spacing.xs,
        )
        layout.setSpacing(0)

        self._step_labels: list[QLabel] = []
        for i, step_name in enumerate(steps):
            if i > 0:
                arrow = QLabel("  ──→  ")
                arrow.setStyleSheet(
                    f"color: {TOKENS.colors.pipeline_connector}; "
                    f"font-size: {TOKENS.font_size.caption}px; "
                    f"border: none;"
                )
                layout.addWidget(arrow)

            label = QLabel(f"  {step_name}  ")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_step_style(label, "idle")
            layout.addWidget(label)
            self._step_labels.append(label)

        layout.addStretch()

    def set_step_state(self, index: int, state: str) -> None:
        if 0 <= index < len(self._step_labels):
            self._apply_step_style(self._step_labels[index], state)

    def reset(self) -> None:
        for label in self._step_labels:
            self._apply_step_style(label, "idle")

    @staticmethod
    def _apply_step_style(label: QLabel, state: str) -> None:
        styles = {
            "idle":   (TOKENS.colors.text_disabled, "transparent", TOKENS.colors.border_default),
            "active": (TOKENS.colors.text_on_accent, TOKENS.colors.accent_primary, TOKENS.colors.accent_primary),
            "done":   (TOKENS.colors.accent_success, "rgba(16,185,129,0.15)", TOKENS.colors.accent_success),
            "error":  (TOKENS.colors.accent_error, "rgba(239,68,68,0.15)", TOKENS.colors.accent_error),
        }
        color, bg, border = styles.get(state, styles["idle"])
        label.setStyleSheet(
            f"color: {color}; background: {bg}; "
            f"border: 1px solid {border}; "
            f"border-radius: {TOKENS.radius.sm}px; "
            f"font-size: {TOKENS.font_size.caption}px; "
            f"font-weight: 500; padding: 2px 8px;"
        )
