"""Chat Workspace — чат с LLM. Строки через i18n, retranslate_ui() без пересоздания."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QScrollArea, QSizePolicy, QSlider, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

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

        self._role_label = role_label
        self._content_label = content_label


class ChatWorkspace(BaseWorkspace):
    # (message, system, model_id, temperature, max_tokens)
    send_requested = Signal(str, str, str, float, int)
    stop_requested = Signal()
    clear_requested = Signal()

    def workspace_id(self) -> str:
        return "chat"

    def _pipeline_steps(self) -> list[str]:
        return [
            tr("step_user"), tr("step_sysctx"), tr("step_llm_api"),
            tr("step_stream"), tr("step_response"),
        ]

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            f"QToolBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: {TOKENS.spacing.sm}px; spacing: {TOKENS.spacing.sm}px; }}"
        )
        self._model_lbl = QLabel(tr("chat_model"))
        self._model_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        tb.addWidget(self._model_lbl)
        self._model_selector = ModelSelector(category="llm", placeholder="Select LLM…")
        tb.addWidget(self._model_selector)
        tb.addSeparator()

        self._temp_lbl = QLabel(tr("chat_temp"))
        self._temp_lbl.setStyleSheet(f"color: {TOKENS.colors.text_secondary}; border: none;")
        tb.addWidget(self._temp_lbl)
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 200)
        self._temp_slider.setValue(70)
        self._temp_slider.setFixedWidth(120)
        tb.addWidget(self._temp_slider)
        self._temp_value = QLabel("0.70")
        self._temp_value.setFixedWidth(40)
        self._temp_value.setStyleSheet(f"color: {TOKENS.colors.accent_secondary}; border: none;")
        self._temp_slider.valueChanged.connect(lambda v: self._temp_value.setText(f"{v/100:.2f}"))
        tb.addWidget(self._temp_value)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._btn_clear = QToolButton()
        self._btn_clear.setText(tr("chat_clear"))
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
        self._scroll = scroll

        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setSpacing(TOKENS.spacing.sm)
        self._chat_layout.setContentsMargins(
            TOKENS.spacing.lg, TOKENS.spacing.lg,
            TOKENS.spacing.lg, TOKENS.spacing.lg,
        )

        # Приветственное сообщение (переводится вместе с языком)
        self._greeting_bubble = ChatBubble("assistant", tr("chat_greeting"))
        self._chat_layout.addWidget(self._greeting_bubble)

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
        self._input.setPlaceholderText(tr("chat_input_ph"))
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

        self._sys_group = CollapsibleGroup(tr("chat_sys_block"), expanded=True)
        sys_layout = QVBoxLayout()
        self._system_prompt = QPlainTextEdit()
        self._system_prompt.setPlaceholderText(tr("chat_sys_ph"))
        self._system_prompt.setMaximumHeight(200)
        sys_layout.addWidget(self._system_prompt)
        self._sys_group.set_content_layout(sys_layout)
        layout.addWidget(self._sys_group)

        self._param_group = CollapsibleGroup(tr("chat_params"))
        pf = QFormLayout()
        self._max_tokens = QComboBox()
        self._max_tokens.addItems(["256", "512", "1024", "2048", "4096", "8192"])
        self._max_tokens.setCurrentText("4096")
        self._max_tokens_lbl = QLabel(tr("chat_max_tokens"))
        pf.addRow(self._max_tokens_lbl, self._max_tokens)
        self._param_group.set_content_layout(pf)
        layout.addWidget(self._param_group)

        self._ctx_group = CollapsibleGroup(tr("chat_context"))
        cf = QVBoxLayout()
        self._ctx_tokens = QLabel()
        self._ctx_cost = QLabel()
        cf.addWidget(self._ctx_tokens)
        cf.addWidget(self._ctx_cost)
        self._ctx_group.set_content_layout(cf)
        layout.addWidget(self._ctx_group)

        layout.addStretch()
        self._update_context_labels()
        return sidebar

    # ── i18n ──

    def retranslate_ui(self) -> None:
        self._model_lbl.setText(tr("chat_model"))
        self._temp_lbl.setText(tr("chat_temp"))
        self._btn_clear.setText(tr("chat_clear"))
        self._input.setPlaceholderText(tr("chat_input_ph"))
        self._sys_group.set_title(tr("chat_sys_block"))
        self._system_prompt.setPlaceholderText(tr("chat_sys_ph"))
        self._param_group.set_title(tr("chat_params"))
        self._max_tokens_lbl.setText(tr("chat_max_tokens"))
        self._ctx_group.set_title(tr("chat_context"))
        self._greeting_bubble._content_label.setText(tr("chat_greeting"))
        self._update_context_labels()
        if self._pipeline_strip is not None:
            self._pipeline_strip.set_steps(self._pipeline_steps())

    def _update_context_labels(self) -> None:
        n = len(self._collect_history())
        self._ctx_tokens.setText(f'{tr("chat_tokens_lbl")} ~{n * 20} / 128k')
        self._ctx_cost.setText(f'{tr("chat_cost_lbl")} $0.000')

    # ── Behavior ──

    def _collect_history(self) -> list[dict]:
        """История в формате [{'role':..., 'content':...}] из текущих пузырей."""
        history = []
        for i in range(self._chat_layout.count()):
            w = self._chat_layout.itemAt(i).widget()
            if isinstance(w, ChatBubble):
                history.append({
                    "role": w._role_label.text().lower(),
                    "content": w._content_label.text(),
                })
        return history

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._chat_layout.addWidget(ChatBubble("user", text))
        self._input.clear()
        self._update_context_labels()
        try:
            max_tokens = int(self._max_tokens.currentText())
        except ValueError:
            max_tokens = 2048
        self.send_requested.emit(
            text,
            self._system_prompt.toPlainText(),
            self._model_selector.current_model_id(),
            self._temp_slider.value() / 100,
            max_tokens,
        )

    def _on_clear(self) -> None:
        self._reset_chat([])
        self.clear_requested.emit()

    def _reset_chat(self, history: list[dict]) -> None:
        """Пересобирает пузыри из истории (пусто → приветствие)."""
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not history:
            self._greeting_bubble = ChatBubble("assistant", tr("chat_greeting"))
            self._chat_layout.addWidget(self._greeting_bubble)
        else:
            for msg in history:
                role = msg.get("role", "assistant")
                if role not in ("user", "assistant"):
                    continue
                self._chat_layout.addWidget(
                    ChatBubble(role, msg.get("content", "")))
            self._greeting_bubble = None
        self._update_context_labels()

    def load_messages(self, history: list[dict]) -> None:
        """Загрузка истории из сохранённого проекта."""
        self._reset_chat(history)

    def system_prompt(self) -> str:
        return self._system_prompt.toPlainText()

    def set_system_prompt(self, text: str) -> None:
        self._system_prompt.setPlainText(text or "")

    def add_message(self, role: str, content: str) -> None:
        self._chat_layout.addWidget(ChatBubble(role, content))
        self._update_context_labels()
        # Автоскролл вниз
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_models(self, models: list[dict]) -> None:
        """Наполняет селектор реальным каталогом активного провайдера."""
        self._model_selector.set_models(models)

    def model_selector(self) -> ModelSelector:
        return self._model_selector

    def set_busy(self, busy: bool) -> None:
        self._btn_send.setEnabled(not busy)
        self._input.setEnabled(not busy)
