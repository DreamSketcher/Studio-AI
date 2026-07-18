"""Settings — правый dock."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup


class SettingsPanel(QWidget):
    settings_changed = None  # placeholder

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        gen_group = CollapsibleGroup("General")
        gen_form = QFormLayout()
        self._theme = QComboBox()
        self._theme.addItems(["Dark", "Light", "System"])
        gen_form.addRow("Theme:", self._theme)
        self._lang = QComboBox()
        self._lang.addItems(["English", "Русский", "日本語", "中文"])
        gen_form.addRow("Language:", self._lang)
        self._auto_save = QCheckBox("Auto-save projects")
        self._auto_save.setChecked(True)
        gen_form.addRow(self._auto_save)
        gen_group.set_content_layout(gen_form)
        layout.addWidget(gen_group)

        perf_group = CollapsibleGroup("Performance")
        perf_form = QFormLayout()
        self._device = QComboBox()
        self._device.addItems(["Auto (GPU if available)", "CPU", "CUDA", "MPS"])
        perf_form.addRow("Device:", self._device)
        self._threads = QSpinBox()
        self._threads.setRange(1, 32)
        self._threads.setValue(4)
        perf_form.addRow("Worker threads:", self._threads)
        self._batch = QSpinBox()
        self._batch.setRange(1, 64)
        self._batch.setValue(1)
        perf_form.addRow("Batch size:", self._batch)
        perf_group.set_content_layout(perf_form)
        layout.addWidget(perf_group)

        paths_group = CollapsibleGroup("Paths")
        paths_form = QFormLayout()
        self._models_path = QPushButton("📁 models/")
        paths_form.addRow("Models dir:", self._models_path)
        self._output_path = QPushButton("📁 outputs/")
        paths_form.addRow("Output dir:", self._output_path)
        paths_group.set_content_layout(paths_form)
        layout.addWidget(paths_group)

        about_group = CollapsibleGroup("About")
        about_form = QVBoxLayout()
        about_form.addWidget(QLabel("AI Studio v0.1.0\nExtracted from XTTS-Studio-AI\nHeadless core + PySide6 UI"))
        about_group.set_content_layout(about_form)
        layout.addWidget(about_group)

        layout.addStretch()
