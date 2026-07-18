# -*- coding: utf-8 -*-
"""Сквозные тесты TTS-контроллера с реальным espeak-бэкендом.

Покрываем:
  * полную цепочку генерация → реальный WAV → история → очередь;
  * склейку нескольких чанков;
  * RVC-гейт (честный отказ, без самообмана);
  * отказ при недоступном бэкенде (без подделки);
  * экспорт wav→mp3 через ffmpeg;
  * очередь задач без демо-данных.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="контроллер — QObject")

from PySide6.QtWidgets import QApplication

from ai_studio_core import espeak_tts, paths

pytestmark = pytest.mark.skipif(
    not espeak_tts.available(), reason="espeak не установлен"
)


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
def sandboxed_dirs(tmp_path, monkeypatch):
    """Перенаправляем outputs/history в tmp — репозиторий не мусорим."""
    out_dir = tmp_path / "outputs"
    hist_path = tmp_path / "history.json"
    monkeypatch.setattr(paths, "OUTPUT_DIR", str(out_dir))
    import ai_studio_core.output_naming as on
    import ai_studio_core.history_store as hs
    monkeypatch.setattr(on, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(hs, "HISTORY_PATH", str(hist_path))
    return {"out": out_dir, "hist": hist_path}


@pytest.fixture()
def ctrl(app):
    from ai_studio_core.ui.controllers.tts_controller import TTSController
    return TTSController()


class TestBackendDetection:
    def test_backend_is_espeak_here(self, ctrl):
        assert ctrl._ensure_backend()
        assert ctrl.backend() == "espeak"

    def test_no_backend_honest_error(self, ctrl, monkeypatch, app):
        import ai_studio_core.ui.controllers.tts_controller as mod
        monkeypatch.setattr(mod, "_detect_backend", lambda: None)
        ctrl._backend = None
        errors = []
        ctrl.error_occurred.connect(errors.append)
        ctrl.on_generate("Hello", {"language": "en"})
        _wait(app, lambda: bool(errors), 5)
        assert errors, "ожидали честную ошибку, а не молчание/подделку"


class TestGenerationReal:
    def test_single_chunk_flow(self, ctrl, sandboxed_dirs, app):
        done, errors = {}, []
        ctrl.generation_complete.connect(lambda p: done.update(path=p))
        ctrl.error_occurred.connect(errors.append)
        ctrl.on_generate("Hello, this is a real synthesis test.",
                         {"language": "en", "speed": 1.0})
        assert _wait(app, lambda: "path" in done, 30), f"errors={errors}"
        path = done["path"]
        assert os.path.exists(path)
        assert path.endswith(".wav")
        assert os.path.getsize(path) > 20_000
        frames, rate, dur = espeak_tts.wav_info(path)
        assert rate == 22050 and dur > 0.5
        assert ctrl.last_output() == path

    def test_pipeline_steps_reach_output(self, ctrl, sandboxed_dirs, app):
        steps = []
        done = []
        ctrl.pipeline_step_changed.connect(lambda i, s: steps.append((i, s)))
        ctrl.generation_complete.connect(lambda p: done.append(True))
        ctrl.on_generate("Pipeline step coverage check.", {"language": "en"})
        assert _wait(app, lambda: bool(done), 30)
        assert (5, "done") in steps or (5, "active") in steps

    def test_multi_chunk_concat(self, ctrl, sandboxed_dirs, app):
        long_text = (
            "This is a fairly long sentence that should be split into chunks. "
            * 12
        )
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate(long_text, {"language": "en", "speed": 1.3})
        assert _wait(app, lambda: bool(done), 60)
        frames, rate, dur = espeak_tts.wav_info(done[0])
        assert dur > 3.0, "длинный текст должен дать заметную длительность"

    def test_mp3_output_via_ffmpeg(self, ctrl, sandboxed_dirs, app):
        pytest.importorskip("pydub")
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("Export to mp3 check.",
                         {"language": "en", "output_format": "mp3"})
        assert _wait(app, lambda: bool(done), 30)
        path = done[0]
        assert path.endswith(".mp3")
        assert os.path.getsize(path) > 1000

    def test_history_recorded(self, ctrl, sandboxed_dirs, app):
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("History persistence check.", {"language": "en"})
        assert _wait(app, lambda: bool(done), 30)
        hist = sandboxed_dirs["hist"]
        assert hist.exists()
        entries = json.loads(hist.read_text(encoding="utf-8"))
        assert len(entries) >= 1
        assert entries[0]["output"] == done[0]


class TestRvcGate:
    def test_rvc_enabled_honest_refusal(self, ctrl, app):
        errors, done = [], []
        ctrl.error_occurred.connect(errors.append)
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("RVC request", {"language": "en", "rvc_enabled": True})
        _wait(app, lambda: bool(errors), 5)
        assert errors
        assert not done, "не должны выдавать обычный синтез за RVC-конвертацию"


class TestQueueIntegration:
    def test_queue_starts_empty_no_demo(self, app):
        from ai_studio_core.ui.controllers.queue_controller import QueueController
        qc = QueueController()
        assert qc.tasks() == [], "в очереди не должно быть вшитых демо-задач"

    def test_task_lifecycle_real(self, ctrl, sandboxed_dirs, app):
        from ai_studio_core.ui.controllers.queue_controller import QueueController
        qc = QueueController()
        ctrl.attach_queue(qc)
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("Queue lifecycle check.", {"language": "en"})
        assert _wait(app, lambda: bool(done), 30)
        tasks = qc.tasks()
        assert len(tasks) == 1
        assert tasks[0].status == "done"
        assert tasks[0].progress == 100
        assert tasks[0].type == "TTS"
        # очистка завершённых
        qc.clear_completed()
        assert qc.tasks() == []

    def test_queue_cancel_marks_status(self, app):
        from ai_studio_core.ui.controllers.queue_controller import QueueController
        qc = QueueController()
        tid = qc.add_task("TTS", "espeak")
        qc.cancel_task(tid)
        assert qc.tasks()[0].status == "cancelled"


class TestExport:
    def test_export_same_format_copy(self, ctrl, sandboxed_dirs, app, tmp_path):
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("Export same-format copy check.", {"language": "en"})
        assert _wait(app, lambda: bool(done), 30)
        target = str(tmp_path / "copy.wav")
        out = ctrl.export_last(target)
        assert os.path.exists(out)
        assert os.path.getsize(out) == os.path.getsize(done[0])

    def test_export_without_generation_fails(self, app, tmp_path):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        fresh = TTSController()
        with pytest.raises(RuntimeError, match="no generated audio"):
            fresh.export_last(str(tmp_path / "x.wav"))

    def test_export_target_needs_extension(self, ctrl, sandboxed_dirs, app, tmp_path):
        done = []
        ctrl.generation_complete.connect(lambda p: done.append(p))
        ctrl.on_generate("Extension validation check.", {"language": "en"})
        assert _wait(app, lambda: bool(done), 30)
        with pytest.raises(ValueError):
            ctrl.export_last(str(tmp_path / "noext") + os.sep)


class TestCancellation:
    def test_aborted_marks_queue_cancelled(self, ctrl, app):
        from ai_studio_core.ui.controllers.queue_controller import QueueController
        qc = QueueController()
        ctrl.attach_queue(qc)
        tid = qc.add_task("TTS", "espeak")
        ctrl._task_id = tid
        out = ctrl._aborted()
        assert out == ""
        assert qc.tasks()[0].status == "cancelled"
