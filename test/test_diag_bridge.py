# -*- coding: utf-8 -*-
"""DiagnosticsBridge (фикс access violation на Windows):

* CUDA-инфо приходит из изолированного сабпроцесса диагностики
  (поля cuda_available/cuda_name в результатах/кэше) — в GUI-процессе
  torch не импортируется НИКОГДА (ни в main, ни в фоновом потоке);
* сигналы diagnostics_updated / cuda_info_changed испускаются строго
  из GUI-потока (queued-слот), ровно один раз на одну проверку;
* повторные kickoff не плодят параллельные сабпроцессы.
"""
from __future__ import annotations

import os
import re
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="мост диагностики — Qt")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_studio_core.ui import diag_bridge as bridge_mod  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def fresh_bridge():
    """Чистый singleton на каждый тест."""
    bridge_mod._BRIDGE = None
    yield bridge_mod
    bridge_mod._BRIDGE = None


def _wait(app, cond, timeout=6.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


class _SignalBag:
    def __init__(self, bridge):
        self.diag = 0
        self.cuda = []
        bridge.diagnostics_updated.connect(lambda: setattr(self, "diag", self.diag + 1))
        bridge.cuda_info_changed.connect(lambda ok, name: self.cuda.append((ok, name)))


class TestWorkerSignals:
    def test_signals_once_and_cuda_from_results(self, app, fresh_bridge, monkeypatch):
        calls = {"n": 0}

        def fake_run(force_refresh=False):
            calls["n"] += 1
            assert force_refresh is False
            return {"torch": True, "tts": True,
                    "cuda_available": True, "cuda_name": "NVIDIA Fake RTX"}

        monkeypatch.setattr(fresh_bridge, "run_full_diagnostics", fake_run)
        bridge = fresh_bridge.get_bridge()
        bag = _SignalBag(bridge)

        bridge.kickoff_refresh(force=False)
        assert _wait(app, lambda: bag.diag == 1), "нет diagnostics_updated после завершения"

        assert bag.cuda == [(True, "NVIDIA Fake RTX")]
        assert bridge.cuda_available() is True
        assert bridge.cuda_device_name() == "NVIDIA Fake RTX"
        assert bridge.component_ok("torch") is True
        assert calls["n"] == 1

        # Повторный kickoff без force — не повторяет проверку
        bridge.kickoff_refresh(force=False)
        _wait(app, lambda: bag.diag > 1, timeout=0.5)
        assert bag.diag == 1
        assert calls["n"] == 1

    def test_force_reruns_after_finish(self, app, fresh_bridge, monkeypatch):
        calls = {"n": 0}
        monkeypatch.setattr(
            fresh_bridge, "run_full_diagnostics",
            lambda force_refresh=False: calls.__setitem__("n", calls["n"] + 1) or {})
        bridge = fresh_bridge.get_bridge()
        bag = _SignalBag(bridge)

        bridge.kickoff_refresh(force=False)
        assert _wait(app, lambda: bag.diag == 1)
        bridge.kickoff_refresh(force=True)
        assert _wait(app, lambda: bag.diag == 2)
        assert calls["n"] == 2

    def test_error_path_still_signals_and_no_cuda(self, app, fresh_bridge, monkeypatch):
        def fake_run(force_refresh=False):
            raise RuntimeError("boom")

        monkeypatch.setattr(fresh_bridge, "run_full_diagnostics", fake_run)
        bridge = fresh_bridge.get_bridge()
        bag = _SignalBag(bridge)

        bridge.kickoff_refresh(force=False)
        assert _wait(app, lambda: bag.diag == 1)
        assert bag.cuda == [(False, "")]
        assert bridge.cuda_available() is False
        assert bridge.component_ok("torch") is False
        assert "boom" in str(bridge.cached_results().get("_error"))

    def test_no_concurrent_refresh(self, app, fresh_bridge, monkeypatch):
        entered = threading.Event()
        release = threading.Event()
        calls = {"n": 0}

        def slow_run(force_refresh=False):
            calls["n"] += 1
            entered.set()
            assert release.wait(5), "тест не отпустил рабочий поток"
            return {"torch": False}

        monkeypatch.setattr(fresh_bridge, "run_full_diagnostics", slow_run)
        bridge = fresh_bridge.get_bridge()
        bag = _SignalBag(bridge)

        bridge.kickoff_refresh(force=True)
        t0 = time.time()
        while not entered.is_set() and time.time() - t0 < 3:
            time.sleep(0.01)
        assert entered.is_set(), "рабочий поток не стартовал"

        # Вторая проверка не должна стартовать, пока первая идёт
        bridge.kickoff_refresh(force=True)
        time.sleep(0.2)
        release.set()
        assert _wait(app, lambda: bag.diag == 1)
        assert calls["n"] == 1, "запустился второй параллельный пробег диагностики"

    def test_no_torch_import_while_refreshing(self, app, fresh_bridge, monkeypatch):
        """Регрессия access violation: ни один импорт torch/TTS в GUI-процессе
        быть не должен — даже если диагностика сообщила, что torch жив."""
        import builtins

        real_import = builtins.__import__
        forbidden = []

        def guarded_import(name, *args, **kwargs):
            root = name.split(".")[0]
            if root in ("torch", "TTS", "torchvision", "torchaudio"):
                forbidden.append(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(fresh_bridge, "run_full_diagnostics",
                            lambda force_refresh=False: {"torch": True,
                                                         "cuda_available": False,
                                                         "cuda_name": ""})
        monkeypatch.setattr(builtins, "__import__", guarded_import)
        bridge = fresh_bridge.get_bridge()
        bag = _SignalBag(bridge)

        bridge.kickoff_refresh(force=True)
        assert _wait(app, lambda: bag.diag == 1)
        assert forbidden == [], f"импорт нативных ML-модулей в GUI-процессе: {forbidden}"

    def test_source_has_no_native_ml_imports(self, fresh_bridge):
        import inspect
        src = inspect.getsource(fresh_bridge)
        assert "_probe_cuda_in_torch" not in src
        for mod in ("torch", "TTS", "torchvision", "torchaudio", "llama_cpp"):
            assert not re.search(rf"^\s*(import|from)\s+{mod}\b", src, re.M), \
                f"diag_bridge не должен импортировать {mod} в GUI-процессе"


class TestCachePredicates:
    def test_predicates_read_cache_without_qt(self, fresh_bridge, monkeypatch):
        monkeypatch.setattr(fresh_bridge, "load_diagnostics_cache",
                            lambda: {"torch": True, "tts": True})
        assert fresh_bridge.torch_available() is True
        assert fresh_bridge.tts_available() is True
        assert fresh_bridge.coqui_available() is True

    def test_predicates_fail_safe(self, fresh_bridge, monkeypatch):
        monkeypatch.setattr(fresh_bridge, "load_diagnostics_cache",
                            lambda: {})
        assert fresh_bridge.torch_available() is False
        assert fresh_bridge.tts_available() is False
        assert fresh_bridge.coqui_available() is False
        # torch нет в кэше → diffusers даже не проверяется
        assert fresh_bridge.diffusers_available() is False

    def test_singleton_identity(self, fresh_bridge):
        assert fresh_bridge.get_bridge() is fresh_bridge.get_bridge()
