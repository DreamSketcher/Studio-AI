"""Chat Workspace — чат с LLM."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QScrollArea,
    QSizePolicy, QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup
from ..widgets.model_selector import ModelSelector
from .base_workspace import BaseWorkspace


class ChatBubble(QFrame):
    def __init__(self, role: str, content: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        is_user = role == "user"
        bg = TOKENS.colors.bg_elevated if is_user else TOKENS.colors.bg_tertiary
        border_color = TOKENS.colors.accent_primary if is_user else TOKENS.colors.border_default

        self.setStyleSheet(
            f"background: {bg}; border-left: 3px solid {border_color}; "
            f"border-radius: {TOKENS.radius.md}px; padding: {TOKENS.spacing.md}px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing.md, TOKENS.spacing.sm,
                                  TOKENS.spacing.md, TOKENS.spacing.sm)

        role_label = QLabel(role.upper())
        role_label.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px; font-weight: 600; border: none;"
        )
        layout.addWidget(role_label)

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setStyleSheet(f"border: none;")
        layout.addWidget(content_label)


class ChatWorkspace(BaseWorkspace):
    send_requested = Signal(str, str, str, float)  # (message, system, model, temperature)
    stop_requested = Signal()
    clear_requested = Signal()

    def workspace_id(self) -> str:
        return "chat"

    def _pipeline_steps(self) -> list[str]:
        return ["User", "System+Context", "LLM API", "Stream", "Response"]

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )
        lbl = QLabel(" Model: ")
        lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        tb.addWidget(lbl)
        self._model_selector = ModelSelector(category="llm", placeholder="Select LLM…")
        tb.addWidget(self._model_selector)
        tb.addSeparator()

        lbl_t = QLabel(" Temp: ")
        lbl_t.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        tb.addWidget(lbl_t)
        from PySide6.QtWidgets import QSlider
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 200)
        self._temp_slider.setValue(70)
        self._temp_slider.setFixedWidth(120)
        tb.addWidget(self._temp_slider)
        self._temp_label = QLabel("0.70")
        self._temp_label.setFixedWidth(40)
        self._temp_label.setStyleSheet(f"color: {TOKENS.colors.accent_secondary}; border: none;")
        self._temp_slider.valueChanged.connect(lambda v: self._temp_label.setText(f"{v/100:.2f}"))
        tb.addWidget(self._temp_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._btn_clear = QToolButton()
        self._btn_clear.setText("🗑  Clear")
        self._btn_clear.clicked.connect(self._on_clear)
        tb.addWidget(self._btn_clear)

        return tb

    def _build_canvas(self) -> QWidget:
        canvas = QWidget()
        layout = QVBoxLayout(canvas)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setSpacing(TOKENS.spacing.sm)
        self._chat_layout.setContentsMargins(
            TOKENS.spacing.lg, TOKENS.spacing.lg,
            TOKENS.spacing.lg, TOKENS.spacing.lg,
        )

        self._chat_layout.addWidget(
            ChatBubble("assistant", "Hello! How can I help you today?")
        )

        scroll.setWidget(self._chat_container)
        layout.addWidget(scroll, stretch=1)

        # Input bar
        bar = QWidget()
        bar.setStyleSheet(
            f"background: {TOKENS.colors.bg_secondary}; "
            f"border-top: 1px solid {TOKENS.colors.border_default};"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(
            TOKENS.spacing.lg, TOKENS.spacing.sm,
            TOKENS.spacing.lg, TOKENS.spacing.sm,
        )
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message…")
        self._input.setMinimumHeight(40)
        self._input.returnPressed.connect(self._on_send)
        bl.addWidget(self._input, stretch=1)

        self._btn_send = QToolButton()
        self._btn_send.setText("⏎")
        self._btn_send.setStyleSheet(
            f"QToolButton {{ background: {TOKENS.colors.accent_primary}; "
            f"color: #fff; border-radius: {TOKENS.radius.md}px; "
            f"padding: {TOKENS.spacing.sm}px {TOKENS.spacing.md}px; "
            f"font-size: 18px; font-weight: bold; border: none; }}"
        )
        self._btn_send.clicked.connect(self._on_send)
        bl.addWidget(self._btn_send)

        layout.addWidget(bar)
        return canvas

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.md, TOKENS.spacing.lg,
            TOKENS.spacing.lg, TOKENS.spacing.lg,
        )

        sys_group = CollapsibleGroup("System Prompt", expanded=True)
        sys_layout = QVBoxLayout()
        self._system_prompt = QPlainTextEdit()
        self._system_prompt.setPlaceholderText("You are a helpful assistant…")
        self._system_prompt.setMaximumHeight(200)
        sys_layout.addWidget(self._system_prompt)
        sys_group.set_content_layout(sys_layout)
        layout.addWidget(sys_group)

        param_group = CollapsibleGroup("Parameters")
        from PySide6.QtWidgets import QFormLayout, QComboBox
        pf = QFormLayout()
        self._max_tokens = QComboBox()
        self._max_tokens.addItems(["256", "512", "1024", "2048", "4096", "8192"])
        self._max_tokens.setCurrentText("4096")
        pf.addRow("Max tokens:", self._max_tokens)
        param_group.set_content_layout(pf)
        layout.addWidget(param_group)

        ctx_group = CollapsibleGroup("Context")
        from PySide6.QtWidgets import QFormLayout
        cf = QVBoxLayout()
        self._ctx_tokens = QLabel("Tokens: 0 / 128k")
        self._ctx_cost = QLabel("Estimated cost: $0.000")
        cf.addWidget(self._ctx_tokens)
        cf.addWidget(self._ctx_cost)
        ctx_group.set_content_layout(cf)
        layout.addWidget(ctx_group)

        layout.addStretch()
        return sidebar

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        bubble = ChatBubble("user", text)
        self._chat_layout.addWidget(bubble)
        self._input.clear()
        self.send_requested.emit(
            text,
            self._system_prompt.toPlainText(),
            self._model_selector.currentText(),
            self._temp_slider.value() / 100,
        )

    def _on_clear(self) -> None:
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.clear_requested.emit()

    def add_message(self, role: str, content: str) -> None:
        self._chat_layout.addWidget(ChatBubble(role, content))

    def set_busy(self, busy: bool) -> None:
        self._btn_send.setEnabled(not busy)
