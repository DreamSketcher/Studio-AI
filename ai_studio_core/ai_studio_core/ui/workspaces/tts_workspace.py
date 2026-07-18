"""TTS Workspace — синтез речи."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QSizePolicy, QSlider,
    QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup
from ..widgets.file_drop_zone import FileDropZone
from ..widgets.model_selector import ModelSelector
from ..widgets.waveform_view import WaveformView
from .base_workspace import BaseWorkspace


def _slider_row(label_text: str, min_val: int, max_val: int, default: int,
               scale: float = 100.0, suffix: str = "×") -> tuple[QWidget, QSlider, QLabel]:
    """Собирает строку 'label [====●====] value' для боковой панели."""
    from PySide6.QtWidgets import QSlider
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
    return row, slider, val


class TTSWorkspace(BaseWorkspace):
    generate_requested = Signal(str, dict)
    stop_requested = Signal()
    export_requested = Signal()

    def workspace_id(self) -> str:
        return "tts"

    def _pipeline_steps(self) -> list[str]:
        return ["Input", "Normalize", "TTS", "RVC", "De-ess", "Output"]

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
        self._btn_generate.setProperty("accent", True)
        self._btn_generate.setStyleSheet(self._accent_btn_style())
        self._btn_generate.clicked.connect(self._on_generate)
        tb.addWidget(self._btn_generate)

        self._btn_stop = QToolButton()
        self._btn_stop.setText("⏹  Stop")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        tb.addWidget(self._btn_stop)

        tb.addSeparator()

        self._btn_export = QToolButton()
        self._btn_export.setText("📥  Export")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self.export_requested.emit)
        tb.addWidget(self._btn_export)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._model_selector = ModelSelector(category="tts", placeholder="Select TTS model…")
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
            label="Drop reference audio here\nor click to browse",
            max_height=100,
        )
        layout.addWidget(self._ref_drop)

        self._text_input = QTextEdit()
        self._text_input.setPlaceholderText(
            "Enter text to synthesize…\n\nSupports multi-paragraph, auto-chunking, and SSML tags."
        )
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
        voice_group = CollapsibleGroup("Voice Parameters", expanded=True)
        vl = QVBoxLayout()
        vl.setSpacing(TOKENS.spacing.xs)

        self._combo_lang = QComboBox()
        self._combo_lang.addItems(["auto", "ru", "en", "es", "fr", "de", "zh", "ja"])
        lang_row = QHBoxLayout()
        lang_row.setSpacing(TOKENS.spacing.sm)
        lbl = QLabel("Language:")
        lbl.setMinimumWidth(100)
        lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        lang_row.addWidget(lbl)
        lang_row.addWidget(self._combo_lang, 1)
        lang_container = QWidget()
        lang_container.setLayout(lang_row)
        vl.addWidget(lang_container)

        self._slider_temp_w = _slider_row("Temperature:", 0, 100, 70)
        self._slider_speed_w = _slider_row("Speed:", 50, 200, 100)
        self._slider_top_p_w = _slider_row("Top-P:", 0, 100, 90)
        self._slider_rep_w = _slider_row("Repetition:", 100, 200, 110)
        self._slider_temp = self._slider_temp_w[1]
        self._slider_speed = self._slider_speed_w[1]
        self._slider_top_p = self._slider_top_p_w[1]
        self._slider_rep = self._slider_rep_w[1]
        for w in (self._slider_temp_w[0], self._slider_speed_w[0],
                  self._slider_top_p_w[0], self._slider_rep_w[0]):
            vl.addWidget(w)

        voice_group.set_content_layout(vl)
        outer.addWidget(voice_group)

        # ── RVC ──
        rvc_group = CollapsibleGroup("RVC Voice Conversion")
        rl = QVBoxLayout()
        rl.setSpacing(TOKENS.spacing.xs)
        self._rvc_enable = QCheckBox("Enable RVC")
        rl.addWidget(self._rvc_enable)
        self._rvc_model = ModelSelector(category="rvc", placeholder="Select RVC…")
        rvc_m_row = QHBoxLayout()
        rvc_m_lbl = QLabel("Model:")
        rvc_m_lbl.setMinimumWidth(100)
        rvc_m_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        rvc_m_row.addWidget(rvc_m_lbl)
        rvc_m_row.addWidget(self._rvc_model, 1)
        rvc_m_container = QWidget()
        rvc_m_container.setLayout(rvc_m_row)
        rl.addWidget(rvc_m_container)
        self._slider_index_w = _slider_row("Index rate:", 0, 100, 75)
        self._slider_index = self._slider_index_w[1]
        rl.addWidget(self._slider_index_w[0])
        self._slider_pitch_w = _slider_row("Pitch shift:", -12, 12, 0, scale=1.0, suffix=" st")
        self._slider_pitch = self._slider_pitch_w[1]
        rl.addWidget(self._slider_pitch_w[0])
        rvc_group.set_content_layout(rl)
        outer.addWidget(rvc_group)

        # ── Output ──
        out_group = CollapsibleGroup("Output")
        ol = QVBoxLayout()
        self._out_format = QComboBox()
        self._out_format.addItems(["WAV", "MP3", "FLAC", "OGG"])
        out_f_row = QHBoxLayout()
        out_f_lbl = QLabel("Format:")
        out_f_lbl.setMinimumWidth(100)
        out_f_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        out_f_row.addWidget(out_f_lbl)
        out_f_row.addWidget(self._out_format, 1)
        out_f_container = QWidget()
        out_f_container.setLayout(out_f_row)
        ol.addWidget(out_f_container)

        self._out_sr = QComboBox()
        self._out_sr.addItems(["22050", "24000", "44100", "48000"])
        self._out_sr.setCurrentText("24000")
        out_s_row = QHBoxLayout()
        out_s_lbl = QLabel("Sample rate:")
        out_s_lbl.setMinimumWidth(100)
        out_s_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        out_s_row.addWidget(out_s_lbl)
        out_s_row.addWidget(self._out_sr, 1)
        out_s_container = QWidget()
        out_s_container.setLayout(out_s_row)
        ol.addWidget(out_s_container)

        self._out_autoplay = QCheckBox("Auto-play after generation")
        ol.addWidget(self._out_autoplay)
        out_group.set_content_layout(ol)
        outer.addWidget(out_group)

        outer.addStretch()
        return sidebar

    def set_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
