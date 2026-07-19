# -*- coding: utf-8 -*-
"""Тесты реальной панели истории: файлы из outputs/, без демо-записей."""
from __future__ import annotations

import os
import struct
import time
import wave

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="панель — Qt-виджет")

from PySide6.QtWidgets import QApplication

from ai_studio_core import paths
from ai_studio_core.ui.panels.history_panel import HistoryPanel, scan_outputs


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _touch_wav(path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(struct.pack("<hhh", 1000, -1000, 1000))


@pytest.fixture()
def outputs_dir(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    out.mkdir()
    monkeypatch.setattr(paths, "OUTPUT_DIR", str(out))
    return out


class TestScanOutputs:
    def test_picks_only_audio_sorted_desc(self, outputs_dir):
        _touch_wav(str(outputs_dir / "a_first.wav"))
        time.sleep(0.02)
        _touch_wav(str(outputs_dir / "b_second.mp3"))
        (outputs_dir / "notes.txt").write_text("junk", encoding="utf-8")
        (outputs_dir / "another.log").write_text("junk", encoding="utf-8")
        entries = scan_outputs(str(outputs_dir))
        assert [e["name"] for e in entries] == ["b_second.mp3", "a_first.wav"]
        assert all(e["type"] == "TTS" for e in entries)

    def test_missing_dir_returns_empty(self, tmp_path):
        assert scan_outputs(str(tmp_path / "nope")) == []

    def test_empty_dir_returns_empty(self, outputs_dir):
        assert scan_outputs(str(outputs_dir)) == []


class TestHistoryPanel:
    def test_panel_lists_real_files(self, app, outputs_dir):
        _touch_wav(str(outputs_dir / "gen1.wav"))
        _touch_wav(str(outputs_dir / "gen2.flac"))
        panel = HistoryPanel()
        names = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert any("gen1.wav" in n for n in names)
        assert any("gen2.flac" in n for n in names)
        panel.deleteLater()

    def test_empty_state_honest_text(self, app, outputs_dir):
        panel = HistoryPanel()
        assert panel._list.count() == 1
        assert "(" in panel._list.item(0).text()  # текст «(no generations yet)»
        panel.deleteLater()

    def test_selection_emits_real_path(self, app, outputs_dir):
        f = str(outputs_dir / "take_me.wav")
        _touch_wav(f)
        panel = HistoryPanel()
        received = []
        panel.item_selected.connect(received.append)
        item = panel._list.item(0)
        panel._list.setCurrentItem(item)
        assert received == [f]
        panel.deleteLater()

    def test_search_filter(self, app, outputs_dir):
        _touch_wav(str(outputs_dir / "alpha.wav"))
        _touch_wav(str(outputs_dir / "beta.wav"))
        panel = HistoryPanel()
        panel._search.setText("alpha")
        visible = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert len(visible) == 1 and "alpha.wav" in visible[0]
        panel._search.setText("")
        assert panel._list.count() == 2
        panel.deleteLater()

    def test_refresh_picks_new_file(self, app, outputs_dir):
        panel = HistoryPanel()
        assert panel._list.item(0).text().startswith("(")
        _touch_wav(str(outputs_dir / "late.wav"))
        panel.refresh()
        assert "late.wav" in panel._list.item(0).text()
        panel.deleteLater()
