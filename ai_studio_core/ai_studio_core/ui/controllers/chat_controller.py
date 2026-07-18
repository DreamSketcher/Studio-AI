"""Контроллер чата с LLM."""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from .base_controller import BaseController


class ChatController(BaseController):
    message_received = Signal(str)      # assistant content
    message_added = Signal(str, str)    # (role, content)
    streaming_chunk = Signal(str)
    generation_started = Signal()
    generation_finished = Signal()

    def __init__(self):
        super().__init__()
        self._client_ready = False

    def _ensure_client(self) -> bool:
        if self._client_ready:
            return True
        try:
            from ai_studio_core.gpt_client import chat as _chat_fn
            self._chat_fn = _chat_fn
            self._client_ready = True
            return True
        except Exception as e:
            self.log_message.emit("WARN", f"LLM client unavailable: {e}")
            return False

    @Slot(str)
    def on_send(self, user_message: str, system_prompt: str = "", model: str = "", temperature: float = 0.7) -> None:
        self.message_added.emit("user", user_message)
        if not self._ensure_client():
            self.message_added.emit("assistant",
                "[Локальный LLM-клиент пока не настроен. Это демонстрационный UI — "
                "интегрируйте api_key и выбранную модель через Settings.]"
            )
            self.status_message.emit("LLM client not configured")
            return
        self.generation_started.emit()
        # Заглушка: реальный вызов и стриминг здесь.
        self.busy_changed.emit(True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, lambda: self._fake_reply(user_message))

    def _fake_reply(self, user_message: str) -> None:
        reply = (
            f"Это демонстрационный ответ на «{user_message[:40]}…».\n\n"
            "Подключите реальный API (openai/groq/anthropic/local-llm) через контроллер "
            "ChatController — для этого достаточно заменить _fake_reply на вызов "
            "ai_studio_core.gpt_client."
        )
        self.message_received.emit(reply)
        self.message_added.emit("assistant", reply)
        self.generation_finished.emit()
        self.busy_changed.emit(False)
        self.status_message.emit("Reply received")

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit("Chat cancelled")

    @Slot()
    def on_clear(self) -> None:
        self.status_message.emit("Chat cleared")
