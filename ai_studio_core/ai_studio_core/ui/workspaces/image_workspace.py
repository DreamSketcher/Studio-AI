"""Image Workspace — генерация изображений (заглушка).

По blueprint UI-слоя этот workspace заявлен как заглушка: разметка есть,
интеграция с image-движком появится позже через контроллер.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QSizePolicy, QSlider, QSpinBox, QTextEdit, QToolBar, QToolButton,
    QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup
from ..widgets.model_selector import ModelSelector
from ..widgets.tag_input import TagInput
from .base_workspace import BaseWorkspace


def _slider_row(label_text: str, min_val: int, max_val: int, default: int,
                fmt: str = "{}") -> tuple[QWidget, QSlider]:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 2, 0, 2)
    lbl = QLabel(label_text)
    lbl.setMinimumWidth(80)
    lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
    h.addWidget(lbl)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(default)
    val = QLabel(fmt.format(default))
    val.setFixedWidth(48)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setStyleSheet(f"color: {TOKENS.colors.accent_secondary}; border: none;")
    slider.valueChanged.connect(lambda v: val.setText(fmt.format(v)))
    h.addWidget(slider, stretch=1)
    h.addWidget(val)
    return row, slider


class ImagePlaceholder(QFrame):
    """Карточка-плейсхолдер под сгенерированное изображение."""

    def __init__(self, index: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border: 1px dashed {TOKENS.colors.border_default}; "
            f"border-radius: {TOKENS.radius.md}px;"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("🖼")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 32px; border: none;")
        layout.addWidget(icon)
        cap = QLabel(f"Image {index}")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setStyleSheet(
            f"color: {TOKENS.colors.text_disabled}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        layout.addWidget(cap)


class ImageWorkspace(BaseWorkspace):
    """Рабочее пространство генерации изображений (каркас)."""

    generate_requested = Signal(str, dict)   # (prompt, params)
    stop_requested = Signal()

    def workspace_id(self) -> str:
        return "image"

    def _pipeline_steps(self) -> list[str]:
        return ["Prompt", "Model", "Sampler", "Upscale", "Output"]

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )

        self._btn_generate = QToolButton()
        self._btn_generate.setText("▶  Generate")
        self._btn_generate.setStyleSheet(
            f"QToolButton {{ background: {TOKENS.colors.accent_primary}; "
            f"color: {TOKENS.colors.text_on_accent}; "
            f"border: none; border-radius: {TOKENS.radius.md}px; "
            f"padding: {TOKENS.spacing.sm}px {TOKENS.spacing.lg}px; "
            f"font-weight: 600; }}"
            f"QToolButton:hover {{ background: #6d28d9; }}"
        )
        self._btn_generate.clicked.connect(self._on_generate)
        tb.addWidget(self._btn_generate)

        self._btn_stop = QToolButton()
        self._btn_stop.setText("⏹  Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        tb.addWidget(self._btn_stop)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._model_selector = ModelSelector(
            category="image", placeholder="Select image model…"
        )
        tb.addWidget(self._model_selector)
        return tb

    def _build_canvas(self) -> QWidget:
        canvas = QWidget()
        layout = QVBoxLayout(canvas)
        layout.setSpacing(TOKENS.spacing.md)
        layout.setContentsMargins(
            TOKENS.spacing.lg, TOKENS.spacing.lg,
            TOKENS.spacing.md, TOKENS.spacing.lg,
        )

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Describe the image to generate…\n\n"
            "Supports prompts, negative prompts and style tags."
        )
        self._prompt.setMinimumHeight(120)
        self._prompt.setMaximumHeight(180)
        layout.addWidget(self._prompt)

        self._tags = TagInput(placeholder="Style tags (Enter to add)…")
        layout.addWidget(self._tags)

        # Сетка-плейсхолдеры результатов
        grid = QGridLayout()
        grid.setSpacing(TOKENS.spacing.md)
        for i in range(4):
            grid.addWidget(ImagePlaceholder(i + 1), i // 2, i % 2)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addLayout(grid, stretch=1)

        return canvas

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.md, TOKENS.spacing.lg,
            TOKENS.spacing.lg, TOKENS.spacing.lg,
        )

        sampler_group = CollapsibleGroup("Sampler")
        sl = QVBoxLayout()
        sl.setSpacing(TOKENS.spacing.xs)

        row_steps, self._slider_steps = _slider_row("Steps:", 1, 150, 28)
        row_cfg, self._slider_cfg = _slider_row("CFG:", 10, 200, 70)
        cfg_val = row_cfg.findChildren(QLabel)[-1]
        cfg_val.setText("7.0")
        self._slider_cfg.valueChanged.connect(
            lambda v: cfg_val.setText(f"{v / 10:.1f}")
        )
        sl.addWidget(row_steps)

        row_seed = QHBoxLayout()
        lbl = QLabel("Seed:")
        lbl.setMinimumWidth(80)
        lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        row_seed.addWidget(lbl)
        self._spin_seed = QSpinBox()
        self._spin_seed.setRange(-1, 2_147_483_647)
        self._spin_seed.setValue(-1)
        self._spin_seed.setSpecialValueText("random")
        row_seed.addWidget(self._spin_seed, 1)
        seed_container = QWidget()
        seed_container.setLayout(row_seed)
        sl.addWidget(row_cfg)
        sl.addWidget(seed_container)

        sampler_group.set_content_layout(sl)
        layout.addWidget(sampler_group)

        size_group = CollapsibleGroup("Output")
        of = QFormLayout()
        self._size = QComboBox()
        self._size.addItems(["512×512", "768×768", "1024×1024", "832×1216", "1216×832"])
        self._size.setCurrentText("1024×1024")
        of.addRow("Size:", self._size)
        self._batch = QSpinBox()
        self._batch.setRange(1, 8)
        self._batch.setValue(1)
        of.addRow("Batch:", self._batch)
        size_group.set_content_layout(of)
        layout.addWidget(size_group)

        layout.addStretch()
        return sidebar

    def _on_generate(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            return
        params = {
            "steps": self._slider_steps.value(),
            "cfg": self._slider_cfg.value() / 10,
            "seed": self._spin_seed.value(),
            "size": self._size.currentText(),
            "batch": self._batch.value(),
            "tags": self._tags.tags(),
        }
        # Заглушка: сигнал есть, контроллер image-движка подключится отдельным этапом.
        self.generate_requested.emit(prompt, params)

    def set_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
