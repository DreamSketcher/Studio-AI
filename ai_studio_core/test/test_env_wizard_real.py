# -*- coding: utf-8 -*-
"""Мастер окружения: проверки реальные, без обещаний скачивания."""
from __future__ import annotations

import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="диалог — Qt")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


class TestRealChecks:
    def test_ffmpeg_check_matches_system(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import _check_ffmpeg
        ok, detail = _check_ffmpeg()
        if shutil.which("ffmpeg"):
            assert ok is True
            assert "ffmpeg" in detail.lower()
        else:
            assert ok is False

    def test_espeak_check_matches_system(self, app):
        from ai_studio_core import espeak_tts
        from ai_studio_core.ui.dialogs.env_setup_wizard import _check_espeak
        ok, _detail = _check_espeak()
        assert ok is espeak_tts.available()

    def test_module_check_honest_for_missing(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import _check_module
        ok, detail = _check_module("module_that_surely_does_not_exist", "hint")
        assert ok is False
        assert "hint" in detail

    def test_module_check_finds_real_one(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import _check_module
        ok, _detail = _check_module("json", "")
        assert ok is True

    def test_run_checks_only_selected(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import run_checks
        results = run_checks(["ffmpeg"])
        assert [r[0] for r in results] == ["ffmpeg"]
        results = run_checks([])
        assert results == []

    def test_run_checks_unknown_name_skipped(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import run_checks
        assert run_checks(["НЛО-компонент"]) == []


class TestWizardFlow:
    def test_progress_page_shows_real_results(self, app):
        from ai_studio_core.ui.dialogs.env_setup_wizard import EnvSetupWizard

        wiz = EnvSetupWizard()
        wiz._components.chk_tts.setChecked(False)     # torch нет в среде — не тянем импорт
        wiz._components.chk_torch.setChecked(False)
        wiz._components.chk_diffusers.setChecked(False)
        wiz._components.chk_cuda.setChecked(False)
        wiz._progress.initializePage()                 # то же, что QWizard.next()

        results = wiz._progress.results
        names = [r[0] for r in results]
        assert names == ["ffmpeg", "espeak-ng"]
        text = wiz._progress._output.toPlainText()
        assert "ffmpeg" in text and "espeak-ng" in text
        # каждая строка помечена результатом
        assert "✅" in text or "❌" in text

        wiz._finish.initializePage()
        summary = wiz._finish._summary.text()
        assert f"Проверено компонентов: {len(results)}" in summary

    def test_all_missing_gives_honest_summary(self, app, monkeypatch):
        import ai_studio_core.ui.dialogs.env_setup_wizard as wizmod

        monkeypatch.setitem(
            wizmod.CHECKS, "ffmpeg", (lambda: (False, "не найден"),))
        wiz = wizmod.EnvSetupWizard()
        wiz._components.chk_ffmpeg.setChecked(True)
        wiz._components.chk_espeak.setChecked(False)
        wiz._components.chk_torch.setChecked(False)
        wiz._components.chk_tts.setChecked(False)
        wiz._components.chk_diffusers.setChecked(False)
        wiz._components.chk_cuda.setChecked(False)
        wiz._progress.initializePage()
        assert wiz._progress.results == [("ffmpeg", False, "не найден")]
        wiz._finish.initializePage()
        assert "Отсутствуют: ffmpeg" in wiz._finish._summary.text()
