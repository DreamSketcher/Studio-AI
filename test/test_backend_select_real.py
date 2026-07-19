# -*- coding: utf-8 -*-
"""Реальный выбор TTS-бэкенда: селектор отражает окружение, выбор честно
применяется, недоступный движок → явная ошибка вместо молчаливой подмены.
"""
from __future__ import annotations

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
    """outputs/history в tmp — репозиторий не мусорим."""
    out_dir = tmp_path / "outputs"
    hist_path = tmp_path / "history.json"
    monkeypatch.setattr(paths, "OUTPUT_DIR", str(out_dir))
    import ai_studio_core.output_naming as on
    import ai_studio_core.history_store as hs
    monkeypatch.setattr(on, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(hs, "HISTORY_PATH", str(hist_path))
    return out_dir


class TestAvailableModels:
    def test_reflects_real_environment(self, app):
        from ai_studio_core.ui.controllers.tts_controller import (
            TTSController, _coqui_available,
        )
        ctrl = TTSController()
        models = ctrl.available_models()
        assert [m["id"] for m in models] == ["auto", "coqui", "espeak"]
        by_id = {m["id"]: m for m in models}
        assert by_id["auto"]["current"] is True
        assert by_id["espeak"]["status"] == (
            "ready" if espeak_tts.available() else "error"
        )
        assert by_id["coqui"]["status"] == (
            "ready" if _coqui_available() else "download"
        )

    def test_current_follows_user_choice(self, app):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        ctrl = TTSController()
        ctrl.select_backend("espeak")
        models = {m["id"]: m for m in ctrl.available_models()}
        assert models["espeak"]["current"] is True
        assert models["auto"]["current"] is False


class TestBackendPinning:
    def test_pinned_espeak_used_for_real_generation(self, app, sandboxed_dirs):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        ctrl = TTSController()
        ctrl.select_backend("espeak")
        done = {}
        ctrl.generation_complete.connect(lambda p: done.update(path=p))
        ctrl.error_occurred.connect(lambda m: done.update(err=m))
        ctrl.on_generate("Pinned backend synthesis check.",
                         {"language": "en", "speed": 1.0})
        assert _wait(app, lambda: "path" in done or "err" in done, 30)
        assert "path" in done, f"генерация упала: {done.get('err')}"
        assert ctrl.backend() == "espeak"
        assert os.path.exists(done["path"])
        assert os.path.getsize(done["path"]) > 0

    def test_pinned_unavailable_backend_honest_error(self, app, monkeypatch):
        """coqui выбран, но недоступен → явная ошибка, файла-пустышки нет."""
        import ai_studio_core.ui.controllers.tts_controller as mod
        monkeypatch.setattr(mod, "_coqui_available", lambda: False)
        ctrl = mod.TTSController()
        errors = []
        ctrl.error_occurred.connect(errors.append)
        ctrl.select_backend("coqui")
        ctrl.on_generate("Hello", {"language": "en"})
        assert errors, "ожидали честную ошибку о недоступном движке"
        assert "coqui" in errors[-1]
        assert ctrl.last_output() is None

    def test_unknown_backend_rejected_with_warn(self, app):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        ctrl = TTSController()
        logs = []
        ctrl.log_message.connect(lambda lvl, msg: logs.append((lvl, msg)))
        ctrl.select_backend("bogus-engine")
        assert ctrl.preferred_backend() == "auto"
        assert any(lvl == "WARN" for lvl, _ in logs)

    def test_auto_falls_back_to_espeak_without_torch(self, app, monkeypatch):
        """auto: coqui недоступен → espeak (реальный fallback, не подделка)."""
        import ai_studio_core.ui.controllers.tts_controller as mod
        monkeypatch.setattr(mod, "_coqui_available", lambda: False)
        ctrl = mod.TTSController()
        assert ctrl._ensure_backend()
        assert ctrl.backend() == "espeak"

    def test_reselect_recomputes_backend(self, app):
        """Смена выбора сбрасывает закэшированный бэкенд."""
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        ctrl = TTSController()
        assert ctrl._ensure_backend()
        first = ctrl.backend()
        ctrl.select_backend("auto")
        assert ctrl._backend is None  # пересчёт при следующей генерации
        assert ctrl._ensure_backend()
        assert ctrl.backend() == first  # в этом окружении снова espeak


class TestRvcModelScan:
    def test_scan_finds_real_pth_files(self, app, tmp_path, monkeypatch):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        mdir = tmp_path / "models"
        (mdir / "rvc").mkdir(parents=True)
        (mdir / "rvc" / "singer_v1.pth").write_bytes(b"fake-weights")
        (mdir / "notes.txt").write_text("not a model")
        monkeypatch.setattr(paths, "MODEL_DIR", str(mdir))

        ctrl = TTSController()
        models = ctrl.rvc_models()
        assert [m["name"] for m in models] == ["singer_v1.pth"]
        assert models[0]["id"].endswith("singer_v1.pth")
        assert models[0]["status"] == "ready"

    def test_scan_empty_dir_is_honestly_empty(self, app, tmp_path, monkeypatch):
        from ai_studio_core.ui.controllers.tts_controller import TTSController
        monkeypatch.setattr(paths, "MODEL_DIR", str(tmp_path))
        ctrl = TTSController()
        assert ctrl.rvc_models() == []
