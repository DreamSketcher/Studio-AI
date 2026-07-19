# -*- coding: utf-8 -*-
"""Тесты живого переключения языка в UI (offscreen Qt).

Регрессия по отчёту «переключение на русский крашит»:
  * SettingsPanel.settings_changed — настоящий Signal (раньше был None →
    AttributeError: 'NoneType' object has no attribute 'emit');
  * полный цикл переключения EN↔RU по реальному главному окну не должен
    бросать исключений, и все подписи реально меняются;
  * выбор языка персистится в QSettings и восстанавливается.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6", reason="GUI-тесты требуют PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from ai_studio_core import i18n
from ai_studio_core.i18n import TRANSLATIONS


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    """Свежее главное окно с изолированным QSettings."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import importlib
    s = QSettings("ai_studio", "studio")
    s.clear()
    s.sync()

    from ai_studio_core.ui.main_window import MainWindow
    w = MainWindow()
    yield w
    w.close()
    w.deleteLater()
    app.processEvents()
    s.clear()
    s.sync()
    i18n.set_language("en")


class TestSettingsPanelSignals:
    def test_settings_changed_is_real_signal(self, window):
        """Краш-регрессия: settings_changed не None, emit() работает."""
        sp = window._settings_widget
        received = []
        sp.settings_changed.connect(received.append)
        sp._emit_settings()
        assert len(received) == 1
        assert isinstance(received[0], dict)
        assert "language" in received[0]

    def test_language_combo_lists_only_available(self, window):
        sp = window._settings_widget
        codes = [sp._lang.itemData(i) for i in range(sp._lang.count())]
        assert codes == list(i18n.LANGUAGES.keys())
        labels = [sp._lang.itemText(i) for i in range(sp._lang.count())]
        assert "Русский" in labels

    def test_language_combo_emits_code_on_switch(self, window):
        sp = window._settings_widget
        received = []
        sp.language_changed.connect(received.append)
        sp._lang.setCurrentIndex(sp._lang.findData("ru"))
        assert received == ["ru"]
        sp._lang.setCurrentIndex(sp._lang.findData("en"))
        assert received == ["ru", "en"]

    def test_emit_after_every_control_is_safe(self, window):
        """Дёргаем все контролы панели — ни один не должен ронять emit-цепочку."""
        sp = window._settings_widget
        sp._theme.setCurrentIndex(0)
        sp._device.setCurrentIndex(0)
        sp._threads.setValue(8)
        sp._batch.setValue(2)
        sp._auto_save.setChecked(False)


class TestLiveSwitch:
    def _switch(self, window, code: str) -> None:
        sp = window._settings_widget
        sp._lang.setCurrentIndex(sp._lang.findData(code))
        QApplication.processEvents()

    def test_tabs_menus_docks_follow_language(self, window):
        self._switch(window, "ru")
        tabs = [window._workspace_tabs.tabText(i) for i in range(window._workspace_tabs.count())]
        assert tabs[0] == TRANSLATIONS["ru"]["tab_tts"]
        assert tabs[1] == TRANSLATIONS["ru"]["tab_chat"]
        assert tabs[2] == TRANSLATIONS["ru"]["tab_image"]
        assert tabs[3] == TRANSLATIONS["ru"]["tab_pipeline"]

        menu_titles = [a.text() for a in window.menuBar().actions()]
        assert TRANSLATIONS["ru"]["menu_file"] in menu_titles
        assert TRANSLATIONS["ru"]["menu_help"] in menu_titles

        dock_titles = [d.windowTitle() for d, _k in window._dock_map]
        assert TRANSLATIONS["ru"]["dock_settings"] in dock_titles
        assert TRANSLATIONS["ru"]["dock_history"] in dock_titles

    def test_workspace_widgets_follow_language(self, window):
        self._switch(window, "ru")
        tts = window._tts_workspace
        assert tts._btn_generate.text() == TRANSLATIONS["ru"]["tts_generate"]
        assert tts._voice_group.title() == TRANSLATIONS["ru"]["tts_voice_params"]
        assert tts._rvc_enable.text() == TRANSLATIONS["ru"]["tts_rvc_enable"]
        chat = window._chat_workspace
        assert chat._btn_clear.text() == TRANSLATIONS["ru"]["chat_clear"]
        assert chat._input.placeholderText() == TRANSLATIONS["ru"]["chat_input_ph"]
        # pipeline strip переведён
        steps = tts.pipeline().steps()
        assert TRANSLATIONS["ru"]["step_normalize"] in steps

    def test_settings_panel_retranslates(self, window):
        sp = window._settings_widget
        self._switch(window, "ru")
        assert sp._gen_group.title() == TRANSLATIONS["ru"]["set_general"]
        assert sp._lang_lbl.text() == TRANSLATIONS["ru"]["set_language"]
        self._switch(window, "en")
        assert sp._gen_group.title() == TRANSLATIONS["en"]["set_general"]

    def test_ping_pong_switching_never_crashes(self, window, app):
        """10 циклов переключения туда-сюда — ни одного исключения."""
        for _ in range(10):
            self._switch(window, "ru")
            app.processEvents()
            self._switch(window, "en")
            app.processEvents()
        assert i18n.get_language() == "en"

    def test_switch_to_ru_all_panels(self, window):
        """Каждая панель/каждый workspace имеет retranslate_ui и он работает."""
        self._switch(window, "ru")
        assert window._model_widget._btn_download.text() == TRANSLATIONS["ru"]["hub_download"]
        assert window._history_widget._search.placeholderText() == TRANSLATIONS["ru"]["hist_search_ph"]
        q_headers = [
            window._queue_widget._table.horizontalHeaderItem(i).text()
            for i in range(5)
        ]
        assert q_headers[0] == TRANSLATIONS["ru"]["queue_status"]
        assert window._inspector_widget._title.text() == TRANSLATIONS["ru"]["insp_nothing"]


class TestPersistence:
    def test_language_persisted_to_qsettings(self, window):
        sp = window._settings_widget
        sp._lang.setCurrentIndex(sp._lang.findData("ru"))
        s = QSettings("ai_studio", "studio")
        assert s.value("ui/language") == "ru"

    def test_invalid_language_code_ignored(self, window):
        """set_language('de') → False, UI не меняется."""
        window._on_language_changed("de")
        assert i18n.get_language() == "en"
        tabs = [window._workspace_tabs.tabText(i) for i in range(4)]
        assert tabs[0] == TRANSLATIONS["en"]["tab_tts"]


class TestGptLabelsInUIContext:
    def test_provider_labels_russian_after_switch(self, window):
        from ai_studio_core import gpt_client
        sp = window._settings_widget
        sp._lang.setCurrentIndex(sp._lang.findData("ru"))
        assert gpt_client.PROVIDERS["groq"]["label"] == TRANSLATIONS["ru"]["prov_groq"]
