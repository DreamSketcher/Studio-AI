"""Контроллер чата с LLM.

Рабочий каркас: история диалога, обращение к gpt_client в фоновом потоке,
отсутствие каких-либо сгенерированных-заранее «демо-ответов».
Когда API-ключ не настроен — пользователь получает честное уведомление.
Полная интеграция (потоковые ответы, выбор провайдера) — отдельным этапом.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from ai_studio_core.i18n import t as tr

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
        # User-пузырь уже отрисован workspace'ом, повторно не добавляем,
        # иначе в UI появится дубликат сообщения.
        if not self._ensure_client():
            self.message_added.emit("assistant", tr("ctl_llm_missing"))
            self.status_message.emit(tr("ctl_llm_missing"))
            return
        self.generation_started.emit()

        def _call(progress_callback=None, cancel_check=None) -> str:
            if cancel_check and cancel_check():
                return ""
            return self._chat_fn(user_message, system=system_prompt or None)

        worker = self._run_in_background(_call)
        worker.result.connect(self._on_reply)

    @Slot(object)
    def _on_reply(self, reply) -> None:
        if not reply:
            return
        self.message_received.emit(reply)
        self.message_added.emit("assistant", reply)
        self.generation_finished.emit()
        self.status_message.emit(tr("ctl_reply_received"))

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit(tr("ctl_chat_cancelled"))

    @Slot()
    def on_clear(self) -> None:
        self.status_message.emit(tr("ctl_chat_cleared"))
