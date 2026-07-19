# -*- coding: utf-8 -*-
"""CUDA-инфо в диагностике: собирается ТОЛЬКО в изолированном сабпроцессе
(run_full_diagnostics), передаётся маркером CUDA_RESULT в stdout,
складывается в отдельный блок кэша cache["cuda"] и доставляется
вызывающим кодом как результаты cuda_available/cuda_name.

Зачем: опрос torch.cuda.* в GUI-процессе — это import torch, а access
violation на битом torch убивает процесс целиком (Windows, PySide6).
"""
from __future__ import annotations

import json
import sys
import types

import pytest


def _ns_run(fn):
    """Подмена модуля subprocess внутри diagnostics: только run(), неглобально."""
    return types.SimpleNamespace(run=fn)

from ai_studio_core.env_core import diagnostics

_ALL_OK = {
    "numpy": True, "torch": True, "torchaudio": True, "torchvision": True,
    "tts": True, "soundfile": True, "pygame": True, "customtkinter": True,
    "num2words": True, "cryptography": True, "llama_cpp": True,
    "rvc_python": True,
}


@pytest.fixture()
def diag_paths(tmp_path, monkeypatch):
    """Изоляция: кэш, site-packages и лог-записи — в tmp."""
    sp = tmp_path / "site-packages"
    sp.mkdir()
    monkeypatch.setattr(diagnostics, "DIAG_CACHE_PATH",
                        str(tmp_path / ".env_diagnostics_cache.json"))
    monkeypatch.setattr(diagnostics, "SITE_PACKAGES", str(sp))
    monkeypatch.setattr(diagnostics, "PYTHON_EXE", sys.executable)
    monkeypatch.setattr(diagnostics, "write_log", lambda *a, **k: None)
    monkeypatch.setattr(diagnostics, "_clean_dataclasses_backport", lambda: 0)
    return tmp_path


def _fake_proc(results: dict, cuda: dict | None):
    out = []
    if cuda is not None:
        out.append("CUDA_RESULT=" + json.dumps(cuda))
    out.append("SUB_RESULT=" + json.dumps(results))

    class _Proc:
        stdout = "\n".join(out) + "\n"
        stderr = ""
    return _Proc()


class TestCudaMarkerParsing:
    def test_cuda_parsed_attached_and_cached(self, diag_paths, monkeypatch):
        calls = {"n": 0}

        def fake_run(cmd, capture_output, text, timeout, env):
            calls["n"] += 1
            assert cmd[0] == sys.executable and cmd[1] == "-c"
            return _fake_proc(dict(_ALL_OK), {"available": True, "name": "NVIDIA RTX Fake"})

        monkeypatch.setattr(diagnostics, "subprocess", _ns_run(fake_run))
        res = diagnostics.run_full_diagnostics(force_refresh=True)

        assert calls["n"] == 1
        assert res["cuda_available"] is True
        assert res["cuda_name"] == "NVIDIA RTX Fake"
        # Компоненты не пострадали
        assert res["torch"] is True and res["numpy"] is True

        # В кэше CUDA лежит ОТДЕЛЬНЫМ блоком, а не внутри results
        with open(diagnostics.DIAG_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        assert cache["cuda"] == {"available": True, "name": "NVIDIA RTX Fake"}
        assert "cuda_available" not in cache["results"]

        # Второй вызов без force — читает кэш, сабпроцесс не запускается,
        # но cuda-ключи присутствуют
        res2 = diagnostics.run_full_diagnostics(force_refresh=False)
        assert calls["n"] == 1
        assert res2["cuda_available"] is True
        assert res2["cuda_name"] == "NVIDIA RTX Fake"

        # И load_diagnostics_cache отдаёт те же ключи
        res3 = diagnostics.load_diagnostics_cache()
        assert res3["cuda_available"] is True
        assert res3["cuda_name"] == "NVIDIA RTX Fake"

    def test_cache_without_cuda_block_gives_false(self, diag_paths, monkeypatch):
        """Старый кэш (до появления CUDA-блока) — честные False, без ошибок."""
        sp = diagnostics.SITE_PACKAGES
        import os
        cache_data = {
            "python_exe": diagnostics.PYTHON_EXE,
            "site_packages_mtime": os.path.getmtime(sp),
            "site_packages_count": len(os.listdir(sp)),
            "timestamp": 123.0,
            "results": dict(_ALL_OK),
        }
        with open(diagnostics.DIAG_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        monkeypatch.setattr(diagnostics.subprocess, "run",
                            lambda *a, **k: pytest.fail("сабпроцесс не должен запускаться"))
        res = diagnostics.run_full_diagnostics(force_refresh=False)
        assert res["cuda_available"] is False
        assert res["cuda_name"] == ""

    def test_cuda_requires_live_torch(self, diag_paths, monkeypatch):
        """Флаг available из сабпроцесса игнорируется, если torch не жив."""
        results = dict(_ALL_OK)
        results["torch"] = "ImportError: DLL load failed"
        monkeypatch.setattr(
            diagnostics, "subprocess",
            _ns_run(lambda *a, **k: _fake_proc(results, {"available": True, "name": "Lying"})))
        res = diagnostics.run_full_diagnostics(force_refresh=True)
        assert res["cuda_available"] is False
        assert res["cuda_name"] == "Lying"  # имя транспортируем, флаг — нет

    def test_missing_cuda_marker_gives_false(self, diag_paths, monkeypatch):
        monkeypatch.setattr(
            diagnostics, "subprocess",
            _ns_run(lambda *a, **k: _fake_proc(dict(_ALL_OK), None)))
        res = diagnostics.run_full_diagnostics(force_refresh=True)
        assert res["cuda_available"] is False
        assert res["cuda_name"] == ""


class TestRealProbe:
    def test_real_subprocess_probe_emits_cuda_marker(self, diag_paths):
        """Реальный прогон сабпроцесса-пробы: маркер CUDA_RESULT разобран,
        результат содержит cuda-ключи. В этой среде torch нет → False.
        Скрытая проверка: GUI-процесс этот импорт torch сам НЕ делает."""
        import builtins
        real_import = builtins.__import__
        forbidden = []

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in ("torch", "TTS"):
                forbidden.append(name)
            return real_import(name, *args, **kwargs)

        saved = builtins.__import__
        builtins.__import__ = guarded_import
        try:
            res = diagnostics.run_full_diagnostics(force_refresh=True)
        finally:
            builtins.__import__ = saved

        assert forbidden == [], f"нативный ML-импорт в GUI-процессе: {forbidden}"
        assert "numpy" in res and "cuda_available" in res
        assert res["numpy"] is True                      # numpy в среде есть
        assert res["cuda_available"] is False            # torch в среде нет
        assert res["cuda_name"] == ""
