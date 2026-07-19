# -*- coding: utf-8 -*-
"""Регрессия STAGE_17: Qt message handler не должен собираться GC.

PySide6: qInstallMessageHandler хранит голый указатель — если Python-callable
умрёт, Qt позовёт освобождённый объект -> access violation (Windows) /
segfault. Поэтому ui.app держит глобальную ссылку _QT_MSG_HANDLER.
"""
from __future__ import annotations

import gc
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="Qt message handler — Qt")

from PySide6.QtCore import qInstallMessageHandler, qWarning  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _restore_handler():
    qInstallMessageHandler(None)


def test_handler_survives_gc_and_logs_qt_warning(app, monkeypatch):
    from ai_studio_core.ui import app as app_mod
    from ai_studio_core import logging_utils

    captured = []
    monkeypatch.setattr(logging_utils, "write_log", lambda t: captured.append(t))
    monkeypatch.setattr(app_mod, "write_log", lambda t: captured.append(t))

    try:
        app_mod._install_qt_log_handler()
        # Условие краша из STAGE_16: локальное замыкание умерло после return
        gc.collect()
        qWarning("test-handler-regression-probe")
        assert any("QT-WARN" in line and "test-handler-regression-probe" in line
                   for line in captured), captured
        assert app_mod._QT_MSG_HANDLER is not None
    finally:
        _restore_handler()


def test_handler_reference_is_global(app):
    import inspect
    from ai_studio_core.ui import app as app_mod

    src = inspect.getsource(app_mod._install_qt_log_handler)
    assert "_QT_MSG_HANDLER" in src, "handler должен сохраняться в глобал"
