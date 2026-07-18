# -*- coding: utf-8 -*-
"""Этап 10 (часть 2): сохранение/загрузка проекта, реальный Pipeline Run,
честный гейт Image-бэкенда, реальные показатели статус-бара.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="QObject/UI")

from PySide6.QtWidgets import QApplication

from ai_studio_core import espeak_tts, paths

need_espeak = pytest.mark.skipif(not espeak_tts.available(),
                                 reason="espeak не установлен")


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


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    """MainWindow с изолированными QSettings."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PySide6.QtCore import QSettings
    QSettings("ai_studio", "studio").clear()
    from ai_studio_core.ui.main_window import MainWindow
    return MainWindow()


# ── Проект: реальный JSON roundtrip ──────────────────────────────────────────

class TestProjectPersistence:
    def test_save_load_roundtrip_restores_state(self, window, tmp_path):
        w = window
        w._tts_workspace.set_text("Текст проекта для сохранения")
        w._tts_workspace._combo_lang.setCurrentText("ru")
        w._tts_workspace._slider_speed.setValue(150)
        w._chat_workspace.set_system_prompt("SYS-P")
        w._chat_ctrl.set_history([
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ])
        w._chat_workspace.load_messages(w._chat_ctrl.history())

        path = str(tmp_path / "proj.json")
        w.save_project_to(path)
        raw = json.loads(open(path, encoding="utf-8").read())
        assert raw["version"] == 1
        assert raw["tts"]["text"] == "Текст проекта для сохранения"
        assert len(raw["chat"]["history"]) == 2

        # Портим состояние и грузим обратно
        w._clear_project()
        assert w._tts_workspace.text() == ""
        assert w._chat_ctrl.history() == []

        w.load_project_from(path)
        assert w._tts_workspace.text() == "Текст проекта для сохранения"
        assert w._tts_workspace._combo_lang.currentText() == "ru"
        assert w._tts_workspace._slider_speed.value() == 150
        assert w._chat_ctrl.history() == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        assert w._chat_workspace.system_prompt() == "SYS-P"

    def test_load_rejects_non_project_json(self, window, tmp_path):
        path = tmp_path / "garbage.json"
        path.write_text('{"foo": 42}', encoding="utf-8")
        with pytest.raises(ValueError):
            window.load_project_from(str(path))

    def test_new_project_clears_canvas(self, window):
        w = window
        w._tts_workspace.set_text("something")
        w._chat_ctrl.set_history([{"role": "user", "content": "x"}])
        w._on_new_project()
        assert w._tts_workspace.text() == ""
        assert w._chat_ctrl.history() == []
        # После очистки остаётся только приветствие
        bubbles = w._chat_workspace._collect_history()
        assert len(bubbles) == 1 and bubbles[0]["role"] == "assistant"


# ── Pipeline Run: та же реальная цепочка, ноды подсвечиваются ───────────────

@need_espeak
class TestPipelineRunReal:
    def test_run_produces_real_wav_and_lights_nodes(self, app, tmp_path, monkeypatch):
        out_dir = tmp_path / "outputs"
        monkeypatch.setattr(paths, "OUTPUT_DIR", str(out_dir))
        import ai_studio_core.output_naming as on
        import ai_studio_core.history_store as hs
        monkeypatch.setattr(on, "OUTPUT_DIR", str(out_dir))
        monkeypatch.setattr(hs, "HISTORY_PATH", str(tmp_path / "history.json"))

        from ai_studio_core.ui.controllers.tts_controller import TTSController
        from ai_studio_core.ui.workspaces.pipeline_workspace import PipelineWorkspace

        ctrl = TTSController()
        ws = PipelineWorkspace()
        # Проводка как в MainWindow
        ws.run_requested.connect(
            lambda text: ctrl.on_generate(text, {"language": "en", "speed": 1.0}))
        ws.stop_requested.connect(ctrl.on_stop)
        ctrl.pipeline_step_changed.connect(ws.set_node_state)
        ctrl.generation_started.connect(ws.reset_nodes)

        done = {}
        ctrl.generation_complete.connect(lambda p: done.update(path=p))
        ctrl.error_occurred.connect(lambda m: done.update(err=m))

        ws._input.setPlainText("Pipeline run produces real audio output.")
        ws._on_run()
        assert _wait(app, lambda: "path" in done or "err" in done, 30)
        assert "path" in done, f"упало: {done.get('err')}"
        assert os.path.exists(done["path"])
        assert os.path.getsize(done["path"]) > 0

        # Ноды реально отсветили ход выполнения: Input/Normalize/TTS/Output = done
        states = [ws._nodes[i]._state for i in range(6)]
        assert states[0] == "done"   # Input
        assert states[1] == "done"   # Normalize
        assert states[2] == "done"   # TTS
        assert states[5] == "done"   # Output
        assert ctrl.backend() == "espeak"

    def test_node_state_api_bounds(self, app):
        from ai_studio_core.ui.workspaces.pipeline_workspace import PipelineWorkspace
        ws = PipelineWorkspace()
        ws.set_node_state(2, "active")
        ws.set_node_state(-1, "done")    # за границами — молча игнор
        ws.set_node_state(99, "done")
        ws.set_node_states(["done"] * 6)
        ws.reset_nodes()


# ── Image: честный гейт без заглушки-картинки ────────────────────────────────

class TestImageGate:
    def test_missing_backend_honest_error_no_files(self, app, tmp_path, monkeypatch):
        import ai_studio_core.ui.controllers.image_controller as ic
        from ai_studio_core.i18n import t as tr

        monkeypatch.setattr(ic, "_diffusers_available", lambda: False)
        monkeypatch.setattr(paths, "OUTPUT_DIR", str(tmp_path / "outputs"))
        ctrl = ic.ImageController()
        errors, ready = [], []
        ctrl.error_occurred.connect(errors.append)
        ctrl.image_ready.connect(ready.append)
        ctrl.on_generate("a cat in space", {"steps": 5})
        assert errors == [tr("ctl_img_missing")]
        assert ready == [], "фальшивого «результата» не появилось"
        assert ctrl.last_image() is None
        outdir = tmp_path / "outputs"
        if outdir.exists():
            assert list(outdir.iterdir()) == []

    def test_available_models_reflect_diffusers_presence(self, app):
        import ai_studio_core.ui.controllers.image_controller as ic
        ctrl = ic.ImageController()
        models = ctrl.available_models()
        assert len(models) == 1
        expected = "ready" if ic._diffusers_available() else "download"
        assert models[0]["status"] == expected


# ── Статус-бар: реальные метрики ─────────────────────────────────────────────

class TestStatusBarReal:
    def test_cpu_ram_real_numbers(self, app):
        psutil = pytest.importorskip("psutil")
        from ai_studio_core.ui.widgets.status_bar import ResourceStatusBar

        bar = ResourceStatusBar()
        bar._poll_resources()
        cpu_txt = bar._cpu_label.text()
        ram_txt = bar._ram_label.text()
        assert cpu_txt.startswith("CPU: ") and cpu_txt.endswith("%")
        assert ram_txt.startswith("RAM: ") and ram_txt.endswith("%")
        cpu_val = int(cpu_txt[5:-1])
        assert 0 <= cpu_val <= 100

    def test_gpu_honestly_dash_without_torch(self, app):
        pytest.importorskip("psutil")
        import ai_studio_core.ui.widgets.status_bar as sb
        bar = sb.ResourceStatusBar()
        # В этой среде torch отсутствует → индикатор честно «—»
        try:
            import torch  # noqa
            has_torch = True
        except Exception:
            has_torch = False
        bar._poll_resources()
        if not has_torch:
            assert bar._gpu_label.text() == "GPU: —"
            assert bar._vram_label.text() == "VRAM: — / —"

    def test_queue_size_label_real(self, app):
        pytest.importorskip("psutil")
        from ai_studio_core.ui.widgets.status_bar import ResourceStatusBar
        bar = ResourceStatusBar()
        bar.set_queue_size(3)
        assert bar._queue_label.text() == "Queue: 3"
        bar.set_queue_size(0)
        assert bar._queue_label.text() == "Queue: 0"

    def test_queue_controller_drives_status_bar(self, window):
        """Интеграция: задачи очереди меняют индикатор Queue."""
        qctrl = window._queue_ctrl
        bar = window._resource_bar
        tid = qctrl.add_task("TTS", "espeak", {})
        QApplication.processEvents()
        assert bar._queue_label.text() == "Queue: 1"
        qctrl.cancel_task(tid)
        qctrl.clear_completed()
        QApplication.processEvents()
        assert bar._queue_label.text() == "Queue: 0"
