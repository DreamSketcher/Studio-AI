# -*- coding: utf-8 -*-
"""Отладочные выключатели старта (изоляция нативного access violation):

AI_STUDIO_NO_XP=1   — без experience-слоя (QSoundEffect/пульсы/usage_stats);
AI_STUDIO_NO_DIAG=1 — без фонового потока диагностики;
AI_STUDIO_NO_PS=1   — без периодического опроса psutil;
AI_STUDIO_NO_QSS=1  — без палитры/stylesheet (проверяется в ui.app).
"""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="MainWindow — Qt")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    """Изоляция QSettings/статистики/диаг-моста + чистый singleton."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings("ai_studio", "studio").clear()
    from ai_studio_core.ui import diag_bridge as bridge_mod
    bridge_mod._BRIDGE = None
    from ai_studio_core.ui.experience import stats as xp_stats
    monkeypatch.setattr(xp_stats, "STATS_PATH", str(tmp_path / "usage_stats.json"))
    yield
    bridge_mod._BRIDGE = None


def _wait_ms(app, ms):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.01)


class TestNoXpSwitch:
    def test_no_xp_uses_noop_layer(self, app, clean_env, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_STUDIO_NO_XP", "1")
        monkeypatch.delenv("AI_STUDIO_NO_DIAG", raising=False)
        from ai_studio_core.ui.diag_bridge import load_diagnostics_cache  # noqa: F401
        from ai_studio_core.ui import diag_bridge as bridge_mod
        monkeypatch.setattr(bridge_mod, "run_full_diagnostics",
                            lambda force_refresh=False: {})
        monkeypatch.setattr(bridge_mod, "load_diagnostics_cache", dict)

        from ai_studio_core.ui.main_window import MainWindow, _NoopExperience
        w = MainWindow()
        w.show()
        _wait_ms(app, 500)

        assert isinstance(w._xp, _NoopExperience)
        assert w._xp.handle("anything") is False
        w._usage.record_session(); w._usage.save(); w._usage.record_action("x")
        # usage_stats.json не создаётся — слой полностью обойдён
        assert not (tmp_path / "usage_stats.json").exists()
        w.close()

    def test_default_xp_active(self, app, clean_env, monkeypatch):
        monkeypatch.delenv("AI_STUDIO_NO_XP", raising=False)
        from ai_studio_core.ui import diag_bridge as bridge_mod
        monkeypatch.setattr(bridge_mod, "run_full_diagnostics",
                            lambda force_refresh=False: {})
        monkeypatch.setattr(bridge_mod, "load_diagnostics_cache", dict)

        from ai_studio_core.ui.main_window import MainWindow, _NoopExperience
        w = MainWindow()
        w.show()
        _wait_ms(app, 500)
        assert not isinstance(w._xp, _NoopExperience)
        w.close()


class TestNoDiagSwitch:
    def test_no_diag_never_starts_worker(self, app, clean_env, monkeypatch):
        monkeypatch.setenv("AI_STUDIO_NO_DIAG", "1")
        from ai_studio_core.ui import diag_bridge as bridge_mod

        called = {"n": 0}
        def spy(force_refresh=False):
            called["n"] += 1
            return {}
        monkeypatch.setattr(bridge_mod, "run_full_diagnostics", spy)
        monkeypatch.setattr(bridge_mod, "load_diagnostics_cache", dict)

        from ai_studio_core.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        _wait_ms(app, 600)

        assert called["n"] == 0, "диагностика стартовала при AI_STUDIO_NO_DIAG=1"
        assert bridge_mod.get_bridge()._refresh_started is False
        w.close()


class TestNoPsSwitch:
    def test_no_ps_stops_polling(self, app, clean_env, monkeypatch):
        monkeypatch.setenv("AI_STUDIO_NO_PS", "1")
        from ai_studio_core.ui import diag_bridge as bridge_mod
        monkeypatch.setattr(bridge_mod, "run_full_diagnostics",
                            lambda force_refresh=False: {})
        monkeypatch.setattr(bridge_mod, "load_diagnostics_cache", dict)

        from ai_studio_core.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        _wait_ms(app, 200)
        assert not w._resource_bar._poll_timer.isActive()
        w.close()

    def test_default_polling_active(self, app, clean_env, monkeypatch):
        monkeypatch.delenv("AI_STUDIO_NO_PS", raising=False)
        from ai_studio_core.ui import diag_bridge as bridge_mod
        monkeypatch.setattr(bridge_mod, "run_full_diagnostics",
                            lambda force_refresh=False: {})
        monkeypatch.setattr(bridge_mod, "load_diagnostics_cache", dict)

        from ai_studio_core.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        _wait_ms(app, 200)
        assert w._resource_bar._poll_timer.isActive()
        w.close()
