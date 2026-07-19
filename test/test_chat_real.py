# -*- coding: utf-8 -*-
"""Тесты реального чата без каких-либо заглушек.

Поднимаем настоящий OpenAI-совместимый HTTP-сервер на 127.0.0.1 (loopback —
единственный случай, когда gpt_client разрешает http://) и проверяем всю цепочку:

  gpt_client.chat  →  реальный HTTP-запрос  →  реальный ответ
  ChatController   →  worker-поток  →  message_received / история
  SettingsPanel    →  реальная персистентность провайдера/ключа
  ChatWorkspace    →  честные id модели/max_tokens в send_requested
  отказные ветки   →  честный AIUnavailable, Никакой фабрикации ответов
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ai_studio_core.gpt_client as gpt_client
from ai_studio_core.gpt_client import AIUnavailable
from ai_studio_core.i18n import t as tr

pytest.importorskip("PySide6", reason="контроллер и панели — Qt-объекты")

from PySide6.QtWidgets import QApplication


# ── Реальный loopback LLM-сервер ───────────────────────────────────────────────

class _ChatHandler(BaseHTTPRequestHandler):
    """OpenAI-совместимый /v1/chat/completions с записью всех payload'ов."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.server.recorded.append(payload)

        if self.server.force_status != 200:
            body = json.dumps({"error": {"message": "boom from test server"}}).encode()
            self.send_response(self.server.force_status)
        else:
            users = [m for m in payload["messages"] if m["role"] == "user"]
            reply = "REAL-ECHO: " + (users[-1]["content"] if users else "?")
            body = json.dumps({
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D401 - тишина в тестах
        pass


@pytest.fixture()
def llm_server():
    server = HTTPServer(("127.0.0.1", 0), _ChatHandler)
    server.recorded = []
    server.force_status = 200
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture()
def gpt_env(tmp_path, monkeypatch, llm_server):
    """Изолированные gpt_settings на tmp + кастомный провайдер на loopback."""
    settings_file = tmp_path / "gpt_settings.json"
    monkeypatch.setattr(gpt_client, "_SETTINGS_PATH", str(settings_file))
    monkeypatch.setenv("XTTS_TEST_SECRET_STORE", "1")
    port = llm_server.server_address[1]
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    gpt_client.add_custom_provider(
        "testlocal", "TestLocal", url, ["m-alpha", "m-beta"], "m-alpha"
    )
    return {"url": url, "file": settings_file, "server": llm_server}


@pytest.fixture()
def gpt_configured(gpt_env):
    """Провайдер выбран и ключ сохранён — цепочка провайдеров непустая."""
    gpt_client.set_provider("testlocal")
    gpt_client.set_api_key("test-secret-key", "testlocal")
    return gpt_env


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _wait(app, cond, timeout=30.0):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.02)
    return cond()


# ── gpt_client против реального loopback-сервера ──────────────────────────────

class TestGptClientLoopback:
    def test_chat_roundtrip_parses_real_response(self, gpt_configured):
        reply = gpt_client.chat("ping")
        assert reply == "REAL-ECHO: ping"

    def test_payload_carries_system_history_temperature_maxtokens(self, gpt_configured):
        gpt_client.chat(
            "hello",
            history=[
                {"role": "user", "content": "prev-q"},
                {"role": "assistant", "content": "prev-a"},
            ],
            system="SYS-MARKER",
            temperature=0.42,
            max_tokens=77,
        )
        server = gpt_configured["server"]
        assert len(server.recorded) == 1
        payload = server.recorded[0]
        assert payload["temperature"] == 0.42
        assert payload["max_tokens"] == 77
        roles = [m["role"] for m in payload["messages"]]
        assert roles == ["system", "user", "assistant", "user"]
        assert payload["messages"][0]["content"] == "SYS-MARKER"
        assert payload["messages"][-1]["content"] == "hello"

    def test_selected_model_goes_to_payload(self, gpt_configured):
        gpt_client.set_model("m-beta", "testlocal")
        gpt_client.chat("which model?")
        payload = gpt_configured["server"].recorded[-1]
        assert payload["model"] == "m-beta"

    def test_no_key_anywhere_raises_ai_unavailable(self, gpt_env):
        # Провайдер зарегистрирован, но ни у одного провайдера нет ключа
        with pytest.raises(AIUnavailable, match="провайдер"):
            gpt_client.chat("ping")
        assert gpt_env["server"].recorded == []  # до сети даже не дошли

    def test_server_500_raises_ai_unavailable_not_crash(self, gpt_configured):
        gpt_configured["server"].force_status = 500
        with pytest.raises(AIUnavailable, match="недоступн"):
            gpt_client.chat("ping")

    def test_key_stored_protected_roundtrip(self, gpt_configured):
        raw = gpt_configured["file"].read_text(encoding="utf-8")
        assert "test-secret-key" not in raw
        assert gpt_client.get_api_key("testlocal") == "test-secret-key"


# ── ChatController end-to-end через реальный сервер ───────────────────────────

class TestChatControllerReal:
    def test_two_turns_history_accumulates(self, app, gpt_configured):
        from ai_studio_core.ui.controllers.chat_controller import ChatController

        ctrl = ChatController()
        replies, added, busy = [], [], []
        ctrl.message_received.connect(replies.append)
        ctrl.message_added.connect(lambda role, content: added.append((role, content)))
        ctrl.busy_changed.connect(busy.append)

        # Ход 1: реальные параметры проброшены сквозь всю цепочку
        ctrl.on_send("Hello", system_prompt="SYS", model="m-beta",
                     temperature=0.33, max_tokens=123)
        assert _wait(app, lambda: bool(replies), 30), "нет ответа от сервера"
        assert replies[0] == "REAL-ECHO: Hello"

        payload = gpt_configured["server"].recorded[0]
        assert payload["model"] == "m-beta"
        assert payload["temperature"] == 0.33
        assert payload["max_tokens"] == 123
        assert payload["messages"][0] == {"role": "system", "content": "SYS"}

        assert busy[0] is True and busy[-1] is False  # сняли флаг занятости
        assert ("assistant", "REAL-ECHO: Hello") in added
        history = ctrl.history()
        assert [h["role"] for h in history] == ["user", "assistant"]

        # Ход 2: сервер должен увидеть накопленную историю
        ctrl.on_send("Second")
        assert _wait(app, lambda: len(replies) >= 2, 30)
        assert replies[1] == "REAL-ECHO: Second"
        payload2 = gpt_configured["server"].recorded[-1]
        contents = [(m["role"], m["content"]) for m in payload2["messages"]]
        assert ("user", "Hello") in contents
        assert ("assistant", "REAL-ECHO: Hello") in contents
        assert contents[-1] == ("user", "Second")
        assert len(ctrl.history()) == 4

        # Очистка честная: история пустеет
        ctrl.on_clear()
        assert ctrl.history() == []

    def test_no_provider_honest_chat_message(self, app, gpt_env, monkeypatch):
        """Без ключей: AIUnavailable → сообщение с ⚠ в чат, без фабрикации."""
        from ai_studio_core.ui.controllers.chat_controller import ChatController

        # Прячем ключ, который мог сохранить предыдущий тест в этом файле
        monkeypatch.setattr(gpt_client, "_SETTINGS_PATH",
                            str(gpt_env["file"].parent / "empty_settings.json"))
        ctrl = ChatController()
        added, statuses = [], []
        ctrl.message_added.connect(lambda role, content: added.append((role, content)))
        ctrl.status_message.connect(statuses.append)
        ctrl.error_occurred.connect(lambda m: None)  # базовый слот тоже есть

        ctrl.on_send("Hi")
        assert _wait(app, lambda: bool(added), 30), "ожидали честный отказ"
        role, content = added[-1]
        assert role == "assistant"
        assert content.startswith("⚠")
        assert "AIUnavailable" in content or "провайдер" in content
        # И ложного «ответа модели» не появилось
        assert all(not c.startswith("REAL-ECHO") for _r, c in added)
        assert statuses, "статус тоже должен отражать отказ"

    def test_gate_when_gpt_client_unimportable(self, app, monkeypatch):
        """Ядро LLM не импортируется → честный гейт ctl_llm_missing, без краша."""
        import ai_studio_core.ui.controllers.chat_controller as cc

        monkeypatch.setitem(sys.modules, "ai_studio_core.gpt_client", None)
        ctrl = cc.ChatController()
        added, statuses = [], []
        ctrl.message_added.connect(lambda role, content: added.append((role, content)))
        ctrl.status_message.connect(statuses.append)
        ctrl.on_send("Hi")
        assert added == [("assistant", tr("ctl_llm_missing"))]
        assert statuses == [tr("ctl_llm_missing")]

    def test_available_models_and_select_model(self, app, gpt_configured):
        from ai_studio_core.ui.controllers.chat_controller import ChatController

        ctrl = ChatController()
        models = ctrl.available_models()
        ids = [m["id"] for m in models]
        assert ids == ["m-alpha", "m-beta"]
        assert all(m["provider"] == "TestLocal" for m in models)
        assert all(m["status"] == "ready" for m in models)
        # Текущая модель подсвечена флагом current
        current = [m for m in models if m.get("current")]
        assert len(current) == 1 and current[0]["id"] == "m-alpha"

        ctrl.select_model("m-beta")
        assert gpt_client.get_model("testlocal") == "m-beta"
        models = ctrl.available_models()
        current = [m for m in models if m.get("current")]
        assert current[0]["id"] == "m-beta"


# ── SettingsPanel: реальная персистентность провайдера/ключа ─────────────────

class TestSettingsPanelLLM:
    def test_panel_lists_custom_provider(self, app, gpt_env):
        from ai_studio_core.ui.panels.settings_panel import SettingsPanel

        panel = SettingsPanel()
        ids = [panel._provider.itemData(i) for i in range(panel._provider.count())]
        assert "groq" in ids and "testlocal" in ids

    def test_panel_saves_provider_and_key(self, app, gpt_env):
        from ai_studio_core.ui.panels.settings_panel import SettingsPanel

        panel = SettingsPanel()
        idx = panel._provider.findData("testlocal")
        assert idx >= 0
        panel._provider.setCurrentIndex(idx)
        panel._api_key.setText("panel-secret")
        saved = []
        panel.llm_saved.connect(saved.append)
        panel._save_llm()

        assert saved == ["testlocal"]
        assert gpt_client.get_provider() == "testlocal"
        assert gpt_client.get_api_key("testlocal") == "panel-secret"
        assert panel._api_key.text() == ""  # поле очищено после сохранения
        raw = gpt_env["file"].read_text(encoding="utf-8")
        assert "panel-secret" not in raw    # в JSON ключ не plaintext

    def test_key_state_reflects_reality(self, app, gpt_env):
        from ai_studio_core.ui.panels.settings_panel import SettingsPanel

        panel = SettingsPanel()
        panel._provider.setCurrentIndex(panel._provider.findData("testlocal"))
        assert panel._key_state.text() == tr("set_key_state_missing")

        gpt_client.set_api_key("k2", "testlocal")
        panel._refresh_key_state()
        assert panel._key_state.text() == tr("set_key_state_ok")

    def test_save_with_empty_key_keeps_existing(self, app, gpt_env):
        """Пустое поле ключа не затирает сохранённый ранее ключ."""
        from ai_studio_core.ui.panels.settings_panel import SettingsPanel

        gpt_client.set_api_key("keep-me", "testlocal")
        panel = SettingsPanel()
        panel._provider.setCurrentIndex(panel._provider.findData("testlocal"))
        panel._api_key.setText("")
        panel._save_llm()
        assert gpt_client.get_api_key("testlocal") == "keep-me"


# ── ModelSelector / ChatWorkspace: честные данные без демонстрашек ───────────

class TestModelSelectorReal:
    def test_no_demo_stubs_on_construction(self, app):
        from ai_studio_core.ui.widgets.model_selector import ModelSelector

        for category in ("tts", "llm", "rvc", "image"):
            assert ModelSelector(category=category).count() == 0

    def test_set_models_preselects_current_silently(self, app):
        from ai_studio_core.ui.widgets.model_selector import ModelSelector

        sel = ModelSelector(category="llm")
        seen = []
        sel.model_changed.connect(seen.append)
        sel.set_models([
            {"id": "m1", "name": "Alpha", "provider": "P", "status": "ready"},
            {"id": "m2", "name": "Beta", "provider": "P", "status": "ready",
             "current": True},
        ])
        assert seen == []                     # пересборка не эмитит
        assert sel.current_model_id() == "m2"  # current подсвечен

    def test_user_selection_emits_model_id(self, app):
        from ai_studio_core.ui.widgets.model_selector import ModelSelector

        sel = ModelSelector(category="llm")
        sel.set_models([
            {"id": "m1", "name": "Alpha", "provider": "P", "status": "ready"},
            {"id": "m2", "name": "Beta", "provider": "P", "status": "ready"},
        ])
        seen = []
        sel.model_changed.connect(seen.append)
        sel.setCurrentIndex(1)
        assert seen == ["m2"]

    def test_select_id_programmatic_no_signal(self, app):
        from ai_studio_core.ui.widgets.model_selector import ModelSelector

        sel = ModelSelector(category="llm")
        sel.set_models([
            {"id": "m1", "name": "Alpha", "provider": "P", "status": "ready"},
        ])
        seen = []
        sel.model_changed.connect(seen.append)
        assert sel.select_id("m1") is True
        assert sel.select_id("nope") is False
        assert seen == []

    def test_chat_workspace_emits_real_send_params(self, app):
        from ai_studio_core.ui.workspaces.chat_workspace import ChatWorkspace

        ws = ChatWorkspace()
        ws.set_models([
            {"id": "m1", "name": "Alpha", "provider": "P", "status": "ready"},
            {"id": "m2", "name": "Beta", "provider": "P", "status": "ready",
             "current": True},
        ])
        ws.model_selector().select_id("m1")
        ws._input.setText("привет")
        ws._system_prompt.setPlainText("SYS")
        ws._temp_slider.setValue(42)
        ws._max_tokens.setCurrentText("512")

        got = []
        ws.send_requested.connect(lambda *a: got.append(a))
        ws._on_send()

        assert got == [("привет", "SYS", "m1", 0.42, 512)]
