"""Image Workspace — генерация изображений.

Бэкенд изображений (diffusers/API) подключается через ImageController;
workspace только собирает параметры и эмитит сигналы. Строки — через i18n.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QSizePolicy, QSlider, QSpinBox, QTextEdit, QToolBar, QToolButton,
    QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup
from ..widgets.model_selector import ModelSelector
from ..widgets.tag_input import TagInput
from .base_workspace import BaseWorkspace


def _slider_row(label_text: str, min_val: int, max_val: int, default: int,
                scale: float = 1.0, fmt: str = "{}") -> tuple[QWidget, QSlider, QLabel, QLabel]:
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
    val = QLabel(fmt.format(default / scale))
    val.setFixedWidth(48)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setStyleSheet(f"color: {TOKENS.colors.accent_secondary}; border: none;")
    slider.valueChanged.connect(lambda v: val.setText(fmt.format(v / scale)))
    h.addWidget(slider, stretch=1)
    h.addWidget(val)
    return row, slider, lbl, val


def _field_row(name_lbl: QLabel, field: QWidget) -> QWidget:
    h = QHBoxLayout()
    h.setSpacing(TOKENS.spacing.sm)
    name_lbl.setMinimumWidth(80)
    name_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
    h.addWidget(name_lbl)
    h.addWidget(field, 1)
    container = QWidget()
    container.setLayout(h)
    return container


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
        self._cap = QLabel()
        self._cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cap.setStyleSheet(
            f"color: {TOKENS.colors.text_disabled}; "
            f"font-size: {TOKENS.font_size.caption}px; border: none;"
        )
        layout.addWidget(self._cap)
        self._index = index
        self.retranslate()

    def retranslate(self) -> None:
        self._cap.setText(f'{tr("img_cell")} {self._index}')


class ImageWorkspace(BaseWorkspace):
    """Рабочее пространство генерации изображений."""

    generate_requested = Signal(str, dict)   # (prompt, params)
    stop_requested = Signal()

    def workspace_id(self) -> str:
        return "image"

    def _pipeline_steps(self) -> list[str]:
        return [
            tr("step_prompt"), tr("step_model"), tr("step_sampler"),
            tr("step_upscale"), tr("step_output"),
        ]

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )

        self._btn_generate = QToolButton()
        self._btn_generate.setText(tr("tts_generate"))
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
        self._btn_stop.setText(tr("tts_stop"))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        tb.addWidget(self._btn_stop)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._model_selector = ModelSelector(
            category="image", placeholder=tr("img_model_ph")
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
        self._prompt.setPlaceholderText(tr("img_prompt_ph"))
        self._prompt.setMinimumHeight(120)
        self._prompt.setMaximumHeight(180)
        layout.addWidget(self._prompt)

        self._tags = TagInput(placeholder=tr("img_tags_ph"))
        layout.addWidget(self._tags)

        grid = QGridLayout()
        grid.setSpacing(TOKENS.spacing.md)
        self._cells: list[ImagePlaceholder] = []
        for i in range(4):
            cell = ImagePlaceholder(i + 1)
            self._cells.append(cell)
            grid.addWidget(cell, i // 2, i % 2)
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

        self._sampler_group = CollapsibleGroup(tr("img_sampler"))
        sl = QVBoxLayout()
        sl.setSpacing(TOKENS.spacing.xs)

        self._row_steps = _slider_row(tr("img_steps"), 1, 150, 28)
        self._slider_steps = self._row_steps[1]
        sl.addWidget(self._row_steps[0])

        self._row_cfg = _slider_row(tr("img_cfg"), 10, 200, 70, scale=10.0, fmt="{:.1f}")
        self._slider_cfg = self._row_cfg[1]
        sl.addWidget(self._row_cfg[0])

        self._seed_lbl = QLabel(tr("img_seed"))
        self._spin_seed = QSpinBox()
        self._spin_seed.setRange(-1, 2_147_483_647)
        self._spin_seed.setValue(-1)
        self._spin_seed.setSpecialValueText(tr("img_seed_random"))
        sl.addWidget(_field_row(self._seed_lbl, self._spin_seed))

        self._sampler_group.set_content_layout(sl)
        layout.addWidget(self._sampler_group)

        self._out_group = CollapsibleGroup(tr("img_output_block"))
        ol = QVBoxLayout()
        self._size_lbl = QLabel(tr("img_size"))
        self._size = QComboBox()
        self._size.addItems(["512×512", "768×768", "1024×1024", "832×1216", "1216×832"])
        self._size.setCurrentText("1024×1024")
        ol.addWidget(_field_row(self._size_lbl, self._size))
        self._batch_lbl = QLabel(tr("img_batch"))
        self._batch = QSpinBox()
        self._batch.setRange(1, 8)
        self._batch.setValue(1)
        ol.addWidget(_field_row(self._batch_lbl, self._batch))
        self._out_group.set_content_layout(ol)
        layout.addWidget(self._out_group)

        layout.addStretch()
        return sidebar

    # ── i18n ──

    def retranslate_ui(self) -> None:
        self._btn_generate.setText(tr("tts_generate"))
        self._btn_stop.setText(tr("tts_stop"))
        self._model_selector.setPlaceholderText(tr("img_model_ph"))
        self._prompt.setPlaceholderText(tr("img_prompt_ph"))
        self._sampler_group.set_title(tr("img_sampler"))
        self._row_steps[2].setText(tr("img_steps"))
        self._row_cfg[2].setText(tr("img_cfg"))
        self._seed_lbl.setText(tr("img_seed"))
        self._spin_seed.setSpecialValueText(tr("img_seed_random"))
        self._out_group.set_title(tr("img_output_block"))
        self._size_lbl.setText(tr("img_size"))
        self._batch_lbl.setText(tr("img_batch"))
        for cell in self._cells:
            cell.retranslate()
        if self._pipeline_strip is not None:
            self._pipeline_strip.set_steps(self._pipeline_steps())

    # ── Behavior ──

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
        self.generate_requested.emit(prompt, params)

    def set_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
