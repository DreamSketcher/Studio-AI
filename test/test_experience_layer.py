# -*- coding: utf-8 -*-
"""Experience layer (этап 12): реальные звуки, валидация пресетов,
менеджер событий, статистика и эвристика стартовой вкладки.
"""
from __future__ import annotations

import json
import os
import time
import wave

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="менеджер/пульс — Qt")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _wait_ms(app, ms):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()
        time.sleep(0.01)


# ── Уровень 1: реальные звуки ────────────────────────────────────────────────

class TestTones:
    def test_every_tone_synthesizes_real_wav(self, tmp_path):
        from ai_studio_core.ui.experience import sounds

        for name in sounds.available_tones():
            path = sounds.tone_path(name, cache_dir=str(tmp_path))
            with wave.open(path, "rb") as wf:
                assert wf.getframerate() == sounds.SAMPLE_RATE
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2
                frames = wf.readframes(wf.getnframes())
            assert os.path.getsize(path) > 500, "анти-пустышка"
            import numpy as np
            data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
            assert float(np.abs(data).max()) > 0.05, "анти-тишина"
            expected = sum(d for _f, d in sounds.TONES[name])
            actual = len(data) / sounds.SAMPLE_RATE
            assert abs(actual - expected) < 0.01

    def test_tone_caching_avoids_resynthesis(self, tmp_path):
        from ai_studio_core.ui.experience import sounds
        p1 = sounds.tone_path("tick", cache_dir=str(tmp_path))
        mtime = os.path.getmtime(p1)
        p2 = sounds.tone_path("tick", cache_dir=str(tmp_path))
        assert p1 == p2 and os.path.getmtime(p2) == mtime

    def test_unknown_tone_rejected(self):
        from ai_studio_core.ui.experience import sounds
        with pytest.raises(ValueError, match="unknown tone"):
            sounds.tone_wav("nope")


# ── Уровень 1: пресеты ───────────────────────────────────────────────────────

class TestPresets:
    def test_default_preset_valid(self):
        from ai_studio_core.ui.experience import presets
        mapping = presets.load_preset()
        assert "generation_complete" in mapping
        assert mapping["generation_complete"]["sound"] == "done_chime"
        assert "accent_pulse" in mapping["generation_complete"]

    def test_unknown_event_rejected(self):
        from ai_studio_core.ui.experience import presets
        with pytest.raises(ValueError, match="unknown event"):
            presets.validate_preset({"events": {"turn_off_lights": {}}})

    def test_unknown_action_and_tone_rejected(self):
        from ai_studio_core.ui.experience import presets
        with pytest.raises(ValueError, match="unknown actions"):
            presets.validate_preset({"events": {"app_started": {"fireworks": {}}}})
        with pytest.raises(ValueError, match="unknown tone"):
            presets.validate_preset({"events": {"app_started": {"sound": "bogus"}}})

    def test_merge_user_override(self, tmp_path):
        from ai_studio_core.ui.experience import presets
        base = presets.load_preset()
        user = tmp_path / "user.json"
        user.write_text(json.dumps({"events": {
            "app_started": {"sound": "tick"}}}), encoding="utf-8")
        merged = presets.merge_presets(base, str(user))
        assert merged["app_started"]["sound"] == "tick"
        # остальные события базового пресета не пострадали
        assert merged["generation_complete"] == base["generation_complete"]


# ── Уровень 1: менеджер ──────────────────────────────────────────────────────

class TestExperienceManager:
    def _manager(self):
        from ai_studio_core.ui.experience import events, presets
        from ai_studio_core.ui.experience.manager import ExperienceManager
        calls = {"toast": [], "pulse": [], "play": [], "status": []}
        mgr = ExperienceManager(
            toast_cb=lambda t, v: calls["toast"].append((t, v)),
            pulse_cb=lambda c, ms: calls["pulse"].append((c, ms)),
            status_cb=lambda m: calls["status"].append(m),
        )
        mgr.configure(presets.load_preset())
        mgr._play = lambda name: calls["play"].append(name)  # без аудио-устройства
        return mgr, calls, events

    def test_event_executes_preset_actions(self, app):
        mgr, calls, events = self._manager()
        assert mgr.handle(events.GENERATION_COMPLETE) is True
        assert calls["play"] == ["done_chime"]
        assert calls["pulse"] and calls["pulse"][0][0] == "#10b981"

    def test_sounds_disabled_skips_play_but_keeps_pulse(self, app):
        mgr, calls, events = self._manager()
        mgr.set_sounds_enabled(False)
        mgr.handle(events.GENERATION_COMPLETE)
        assert calls["play"] == []
        assert calls["pulse"], "пульс остаётся — звук отключается отдельно"

    def test_toast_text_resolution(self, app):
        from ai_studio_core.i18n import t as tr
        from ai_studio_core.ui.experience.manager import resolve_text
        # i18n-ключ переводится
        assert resolve_text("exp_queue_drained") == tr("exp_queue_drained")
        # литерал с плейсхолдером
        assert resolve_text("Saved: {output}", {"output": "/tmp/x.json"}) == \
            "Saved: /tmp/x.json"
        # отсутствующий плейсхолдер не роняет
        assert resolve_text("Saved: {missing}") == "Saved: {missing}"

    def test_unknown_event_is_honest_false(self, app):
        mgr, calls, _events = self._manager()
        assert mgr.handle("alien_event") is False
        assert calls == {"toast": [], "pulse": [], "play": [], "status": []}


class TestAccentPulse:
    def test_pulse_shows_then_autohides(self, app):
        from ai_studio_core.ui.experience.manager import AccentPulse
        from PySide6.QtWidgets import QWidget

        host = QWidget()
        host.resize(800, 600)
        host.show()
        bar = AccentPulse(host)
        bar.pulse("#10b981", 200)
        app.processEvents()
        assert bar.isVisible()
        assert bar.width() == 800
        _wait_ms(app, 1000)
        assert not bar.isVisible(), "пульс обязан самоудалиться"
        host.close()


# ── Уровень 2: статистика и эвристика ────────────────────────────────────────

class TestUsageStats:
    def test_record_and_roundtrip(self, tmp_path):
        from ai_studio_core.ui.experience.stats import UsageStats

        path = str(tmp_path / "usage.json")
        s = UsageStats(path=path)
        s.record_session()
        s.record_activation("chat")
        s.record_activation("chat")
        s.record_action("chat_send")
        s.record_backend("espeak")
        s.record_active_seconds(12.5)
        s.save()

        raw = json.loads(open(path, encoding="utf-8").read())
        assert raw["sessions"] == 1
        assert raw["workspace_activations"]["chat"] == 2

        s2 = UsageStats.load(path)
        assert s2.activations()["chat"] == 2
        assert s2.data()["backend_use"] == {"espeak": 1}
        assert s2.data()["session_seconds_total"] == 12.5

    def test_load_missing_file_is_empty_not_crash(self, tmp_path):
        from ai_studio_core.ui.experience.stats import UsageStats
        s = UsageStats.load(str(tmp_path / "none.json"))
        assert s.data()["sessions"] == 0

    def test_junk_fields_ignored_honestly(self, tmp_path):
        from ai_studio_core.ui.experience.stats import UsageStats
        path = tmp_path / "usage.json"
        path.write_text(json.dumps({
            "sessions": 5, "alien": 1,
            "workspace_activations": {"chat": 7, "alien_ws": 99}}), encoding="utf-8")
        s = UsageStats.load(str(path))
        assert s.data()["sessions"] == 5
        assert "alien" not in s.data()
        assert "alien_ws" not in s.activations()

    def test_heuristic_threshold_tie_and_winner(self):
        from ai_studio_core.ui.experience.stats import (
            UsageStats, suggested_start_workspace,
        )
        s = UsageStats(path="unused")
        ws, reason = suggested_start_workspace(s)
        assert ws == "tts" and "недостаточно" in reason

        for _ in range(5):
            s.record_activation("chat")
        s.record_activation("pipeline")
        ws, reason = suggested_start_workspace(s)
        assert ws == "chat" and "5/6" in reason

        s2 = UsageStats(path="unused")
        for _ in range(3):
            s2.record_activation("chat")
        for _ in range(3):
            s2.record_activation("tts")
        ws, reason = suggested_start_workspace(s2)
        assert ws == "tts" and "ничья" in reason


# ── Интеграция: адаптивная стартовая вкладка и тумблер звуков ───────────────

@pytest.fixture()
def window_factory(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from ai_studio_core.ui.experience import stats as xp_stats

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings("ai_studio", "studio").clear()
    stats_file = tmp_path / "usage_stats.json"
    monkeypatch.setattr(xp_stats, "STATS_PATH", str(stats_file))

    def _make(seed_activations: dict | None = None, adaptive: bool = True,
              sounds: bool = True):
        if seed_activations:
            s = xp_stats.UsageStats(path=str(stats_file))
            for ws, n in seed_activations.items():
                for _ in range(n):
                    s.record_activation(ws)
            s.save()
        QSettings("ai_studio", "studio").setValue("ui/adaptive_start_tab", adaptive)
        QSettings("ai_studio", "studio").setValue("ui/exp_sounds", sounds)
        from ai_studio_core.ui.main_window import MainWindow
        return MainWindow()
    return _make


class TestAdaptiveStartIntegration:
    def test_most_used_workspace_becomes_start_tab(self, window_factory):
        w = window_factory(seed_activations={"chat": 6, "tts": 1})
        assert w._workspace_tabs.currentWidget() is w._chat_workspace
        assert w._usage.activations()["chat"] == 6  # программный выбор не засчитан

    def test_toggle_off_gives_default_tab(self, window_factory):
        w = window_factory(seed_activations={"chat": 9}, adaptive=False)
        assert w._workspace_tabs.currentIndex() == 0  # дефолт — TTS

    def test_no_stats_gives_default_tab(self, window_factory):
        w = window_factory()
        assert w._workspace_tabs.currentIndex() == 0

    def test_sounds_toggle_propagates(self, window_factory):
        w = window_factory(sounds=False)
        assert w._xp.sounds_enabled() is False
        w2 = window_factory(sounds=True)
        assert w2._xp.sounds_enabled() is True

    def test_tab_switch_records_activation(self, window_factory):
        w = window_factory()
        chat_idx = w._tab_index_for("chat")
        w._workspace_tabs.setCurrentIndex(chat_idx)
        assert w._usage.activations()["chat"] == 1
        # и на диск тоже
        s2 = w._xp_stats_mod.UsageStats.load()
        assert s2.activations()["chat"] == 1

    def test_queue_drained_event_fires_once(self, window_factory):
        from ai_studio_core.ui.experience import events
        w = window_factory()
        seen = []
        orig = w._xp.handle
        w._xp.handle = lambda e, p=None: seen.append(e) or orig(e, p)
        tid = w._queue_ctrl.add_task("TTS", "espeak", {})
        QApplication.processEvents()
        w._queue_ctrl.set_task_progress(tid, 100, "done")
        QApplication.processEvents()
        assert seen.count(events.QUEUE_DRAINED) == 1
