"""Контроллер чата с LLM — реальная интеграция с ai_studio_core.gpt_client.

  * история диалога ведётся контроллером и передаётся в API;
  * system prompt / temperature / max tokens пробрасываются из сайдбара;
  * вызов идёт в фоновом потоке (UI не блокируется);
  * AIUnavailable (нет ключа/провайдера, сеть) → честное сообщение пользователю,
    никаких сфабрикованных ответов;
  * модель/провайдер берутся из настроек gpt_client (Settings → LLM Provider).
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Slot

from ai_studio_core.i18n import t as tr

from .base_controller import BaseController


class ChatController(BaseController):
    message_received = Signal(str)      # assistant content
    message_added = Signal(str, str)    # (role, content)
    generation_started = Signal()
    generation_finished = Signal()

    def __init__(self):
        super().__init__()
        self._client_ready = False
        self._history: list[dict] = []

    # ── Публичное API ──

    def history(self) -> list[dict]:
        return list(self._history)

    def set_history(self, history: list[dict]) -> None:
        self._history = [dict(h) for h in history if h.get("content")]

    def available_models(self) -> list[dict]:
        """Модели активного провайдера (из его каталога) для ModelSelector."""
        try:
            from ai_studio_core import gpt_client
            pid = gpt_client.get_provider()
            info = gpt_client.get_provider_info(pid)
            configured = bool(gpt_client.get_api_key(pid)) or pid == "local"
            current = gpt_client.get_model(pid)
            status = "ready" if configured else "error"
            out = []
            for m in info.get("models", []):
                out.append({
                    "id": m,
                    "name": m,
                    "provider": info.get("label", pid),
                    "status": status,
                    "current": m == current,
                })
            return out
        except Exception as e:
            self.log_message.emit("WARN", f"model list unavailable: {e}")
            return []

    def select_model(self, model_id: str) -> None:
        """Сохраняет выбранную модель активного провайдера в настройки."""
        try:
            from ai_studio_core import gpt_client
            gpt_client.set_model(model_id)
            self.status_message.emit(f"Model: {model_id}")
        except Exception as e:
            self.log_message.emit("WARN", f"set_model failed: {e}")

    # ── Внутреннее ──

    def _ensure_client(self) -> bool:
        if self._client_ready:
            return True
        try:
            from ai_studio_core.gpt_client import (
                AIUnavailable, chat as _chat_fn,
            )
            self._chat_fn = _chat_fn
            self._ai_unavailable = AIUnavailable
            self._client_ready = True
            return True
        except Exception as e:
            self.log_message.emit("WARN", f"LLM client unavailable: {e}")
            return False

    @Slot(str)
    def on_send(self, user_message: str, system_prompt: str = "",
                model: str = "", temperature: float = 0.7,
                max_tokens: int = 2048) -> None:
        # User-пузырь уже отрисован workspace'ом, повторно не добавляем.
        if not self._ensure_client():
            self.message_added.emit("assistant", tr("ctl_llm_missing"))
            self.status_message.emit(tr("ctl_llm_missing"))
            return

        if model:
            self.select_model(model)

        history = list(self._history)
        self.generation_started.emit()

        def _call(progress_callback=None, cancel_check=None) -> str:
            if cancel_check and cancel_check():
                return ""
            return self._chat_fn(
                user_message,
                history=history,
                system=system_prompt or None,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        worker = self._run_in_background(_call)
        worker.result.connect(self._on_reply)
        worker.error.connect(self._on_call_error)
        self._pending_user = user_message

    @Slot(object)
    def _on_reply(self, reply) -> None:
        if not reply:
            return
        self._history.append({"role": "user", "content": self._pending_user})
        self._history.append({"role": "assistant", "content": reply})
        self.message_received.emit(reply)
        self.message_added.emit("assistant", reply)
        self.generation_finished.emit()
        self.status_message.emit(tr("ctl_reply_received"))

    @Slot(str)
    def _on_call_error(self, message: str) -> None:
        # AIUnavailable и прочие сбои — честно в чат и статус, без краша
        self.message_added.emit("assistant", f"⚠ {message}")
        self.status_message.emit(message[:200])
        self.generation_finished.emit()

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit(tr("ctl_chat_cancelled"))

    @Slot()
    def on_clear(self) -> None:
        self._history.clear()
        self.status_message.emit(tr("ctl_chat_cleared"))
