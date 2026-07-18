"""TTS Workspace — синтез речи.

Все видимые строки — через ai_studio_core.i18n.t();
retranslate_ui() переключает язык без пересоздания виджетов.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QSizePolicy, QSlider,
    QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup
from ..widgets.file_drop_zone import FileDropZone
from ..widgets.model_selector import ModelSelector
from ..widgets.waveform_view import WaveformView
from .base_workspace import BaseWorkspace


def _slider_row(label_text: str, min_val: int, max_val: int, default: int,
                scale: float = 100.0, suffix: str = "×") -> tuple[QWidget, QSlider, QLabel, QLabel]:
    """Собирает строку 'name [====●====] value' для боковой панели.

    Возвращает (row_widget, slider, name_label, value_label) —
    name_label сохраняется для ретрансляции при смене языка.
    """
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 2, 0, 2)
    lbl = QLabel(label_text)
    lbl.setMinimumWidth(100)
    lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
    h.addWidget(lbl)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(default)
    val = QLabel(f"{default/scale:.2f}{suffix}")
    val.setFixedWidth(60)
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val.setStyleSheet(f"color: {TOKENS.colors.accent_secondary}; border: none;")
    slider.valueChanged.connect(lambda v: val.setText(f"{v/scale:.2f}{suffix}"))
    h.addWidget(slider, stretch=1)
    h.addWidget(val)
    return row, slider, lbl, val


def _field_row(name_lbl: QLabel, field: QWidget) -> QWidget:
    """Строка 'name [field]' для сайдбара с сохранением ссылки на name-label."""
    h = QHBoxLayout()
    h.setSpacing(TOKENS.spacing.sm)
    name_lbl.setMinimumWidth(100)
    name_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
    h.addWidget(name_lbl)
    h.addWidget(field, 1)
    container = QWidget()
    container.setLayout(h)
    return container


class TTSWorkspace(BaseWorkspace):
    generate_requested = Signal(str, dict)
    stop_requested = Signal()
    export_requested = Signal()

    def workspace_id(self) -> str:
        return "tts"

    def _pipeline_steps(self) -> list[str]:
        return [
            tr("step_input"), tr("step_normalize"), tr("step_tts"),
            tr("step_rvc"), tr("step_deess"), tr("step_output"),
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
        self._btn_generate.setProperty("accent", True)
        self._btn_generate.setStyleSheet(self._accent_btn_style())
        self._btn_generate.clicked.connect(self._on_generate)
        tb.addWidget(self._btn_generate)

        self._btn_stop = QToolButton()
        self._btn_stop.setText(tr("tts_stop"))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        tb.addWidget(self._btn_stop)

        tb.addSeparator()

        self._btn_export = QToolButton()
        self._btn_export.setText(tr("tts_export"))
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self.export_requested.emit)
        tb.addWidget(self._btn_export)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._model_selector = ModelSelector(category="tts", placeholder=tr("tts_model_ph"))
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

        self._ref_drop = FileDropZone(
            accepted_extensions=[".wav", ".mp3", ".flac", ".ogg"],
            label=tr("tts_drop_label"),
            max_height=100,
        )
        layout.addWidget(self._ref_drop)

        self._text_input = QTextEdit()
        self._text_input.setPlaceholderText(tr("tts_text_ph"))
        self._text_input.setMinimumHeight(180)
        layout.addWidget(self._text_input, stretch=3)

        self._waveform = WaveformView()
        layout.addWidget(self._waveform, stretch=1)

        return canvas

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        outer = QVBoxLayout(sidebar)
        outer.setSpacing(TOKENS.spacing.sm)
        outer.setContentsMargins(
            TOKENS.spacing.md, TOKENS.spacing.lg,
            TOKENS.spacing.lg, TOKENS.spacing.lg,
        )

        # ── Voice Parameters ──
        self._voice_group = CollapsibleGroup(tr("tts_voice_params"), expanded=True)
        vl = QVBoxLayout()
        vl.setSpacing(TOKENS.spacing.xs)

        self._combo_lang = QComboBox()
        self._combo_lang.addItems(["auto", "ru", "en", "es", "fr", "de", "zh", "ja"])
        self._lang_lbl = QLabel(tr("tts_language"))
        vl.addWidget(_field_row(self._lang_lbl, self._combo_lang))

        self._slider_temp_w = _slider_row(tr("tts_temperature"), 0, 100, 70)
        self._slider_speed_w = _slider_row(tr("tts_speed"), 50, 200, 100)
        self._slider_top_p_w = _slider_row(tr("tts_top_p"), 0, 100, 90)
        self._slider_rep_w = _slider_row(tr("tts_repetition"), 100, 200, 110)
        self._slider_temp = self._slider_temp_w[1]
        self._slider_speed = self._slider_speed_w[1]
        self._slider_top_p = self._slider_top_p_w[1]
        self._slider_rep = self._slider_rep_w[1]
        for w in (self._slider_temp_w[0], self._slider_speed_w[0],
                  self._slider_top_p_w[0], self._slider_rep_w[0]):
            vl.addWidget(w)

        self._voice_group.set_content_layout(vl)
        outer.addWidget(self._voice_group)

        # ── RVC ──
        self._rvc_group = CollapsibleGroup(tr("tts_rvc_block"))
        rl = QVBoxLayout()
        rl.setSpacing(TOKENS.spacing.xs)
        self._rvc_enable = QCheckBox(tr("tts_rvc_enable"))
        rl.addWidget(self._rvc_enable)
        self._rvc_model = ModelSelector(category="rvc", placeholder=tr("tts_rvc_ph"))
        self._rvc_model_lbl = QLabel(tr("tts_rvc_model"))
        rl.addWidget(_field_row(self._rvc_model_lbl, self._rvc_model))
        self._slider_index_w = _slider_row(tr("tts_index_rate"), 0, 100, 75)
        self._slider_index = self._slider_index_w[1]
        rl.addWidget(self._slider_index_w[0])
        self._slider_pitch_w = _slider_row(tr("tts_pitch"), -12, 12, 0, scale=1.0, suffix=" st")
        self._slider_pitch = self._slider_pitch_w[1]
        rl.addWidget(self._slider_pitch_w[0])
        self._rvc_group.set_content_layout(rl)
        outer.addWidget(self._rvc_group)

        # ── Output ──
        self._out_group = CollapsibleGroup(tr("tts_output_block"))
        ol = QVBoxLayout()
        self._out_format = QComboBox()
        self._out_format.addItems(["WAV", "MP3", "FLAC", "OGG"])
        self._out_format_lbl = QLabel(tr("tts_format"))
        ol.addWidget(_field_row(self._out_format_lbl, self._out_format))

        self._out_sr = QComboBox()
        self._out_sr.addItems(["22050", "24000", "44100", "48000"])
        self._out_sr.setCurrentText("24000")
        self._out_sr_lbl = QLabel(tr("tts_sample_rate"))
        ol.addWidget(_field_row(self._out_sr_lbl, self._out_sr))

        self._out_autoplay = QCheckBox(tr("tts_autoplay"))
        ol.addWidget(self._out_autoplay)
        self._out_group.set_content_layout(ol)
        outer.addWidget(self._out_group)

        outer.addStretch()
        return sidebar

    # ── i18n ──

    def retranslate_ui(self) -> None:
        self._btn_generate.setText(tr("tts_generate"))
        self._btn_stop.setText(tr("tts_stop"))
        self._btn_export.setText(tr("tts_export"))
        self._model_selector.setPlaceholderText(tr("tts_model_ph"))
        self._ref_drop.set_label(tr("tts_drop_label"))
        self._text_input.setPlaceholderText(tr("tts_text_ph"))

        self._voice_group.set_title(tr("tts_voice_params"))
        self._lang_lbl.setText(tr("tts_language"))
        self._slider_temp_w[2].setText(tr("tts_temperature"))
        self._slider_speed_w[2].setText(tr("tts_speed"))
        self._slider_top_p_w[2].setText(tr("tts_top_p"))
        self._slider_rep_w[2].setText(tr("tts_repetition"))

        self._rvc_group.set_title(tr("tts_rvc_block"))
        self._rvc_enable.setText(tr("tts_rvc_enable"))
        self._rvc_model_lbl.setText(tr("tts_rvc_model"))
        self._rvc_model.setPlaceholderText(tr("tts_rvc_ph"))
        self._slider_index_w[2].setText(tr("tts_index_rate"))
        self._slider_pitch_w[2].setText(tr("tts_pitch"))

        self._out_group.set_title(tr("tts_output_block"))
        self._out_format_lbl.setText(tr("tts_format"))
        self._out_sr_lbl.setText(tr("tts_sample_rate"))
        self._out_autoplay.setText(tr("tts_autoplay"))

        if self._pipeline_strip is not None:
            self._pipeline_strip.set_steps(self._pipeline_steps())

    # ── Behavior ──

    def text(self) -> str:
        return self._text_input.toPlainText()

    def set_text(self, text: str) -> None:
        self._text_input.setPlainText(text)

    def waveform_widget(self) -> WaveformView:
        return self._waveform

    def set_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
        self._btn_export.setEnabled(not busy)

    # ── Helpers ──

    @staticmethod
    def _accent_btn_style() -> str:
        """Стиль основной (accent) кнопки в тулбаре workspace'а."""
        return (
            f"QToolButton {{ background: {TOKENS.colors.accent_primary}; "
            f"color: {TOKENS.colors.text_on_accent}; "
            f"border: none; border-radius: {TOKENS.radius.md}px; "
            f"padding: {TOKENS.spacing.sm}px {TOKENS.spacing.lg}px; "
            f"font-weight: 600; }}"
            f"QToolButton:hover {{ background: #6d28d9; }}"
            f"QToolButton:disabled {{ background: {TOKENS.colors.bg_elevated}; "
            f"color: {TOKENS.colors.text_disabled}; }}"
        )

    def _on_generate(self) -> None:
        """Собирает параметры из сайдбара и эмитит generate_requested."""
        text = self._text_input.toPlainText().strip()
        if not text:
            return
        params = {
            "language": self._combo_lang.currentText(),
            "temperature": self._slider_temp.value() / 100,
            "speed": self._slider_speed.value() / 100,
            "top_p": self._slider_top_p.value() / 100,
            "repetition_penalty": self._slider_rep.value() / 100,
            "rvc_enabled": self._rvc_enable.isChecked(),
            "rvc_model": self._rvc_model.currentText(),
            "rvc_index_rate": self._slider_index.value() / 100,
            "rvc_pitch": self._slider_pitch.value(),
            "output_format": self._out_format.currentText().lower(),
            "sample_rate": int(self._out_sr.currentText()),
            "autoplay": self._out_autoplay.isChecked(),
            "reference_audio": self._ref_drop.current_path(),
        }
        self.generate_requested.emit(text, params)
