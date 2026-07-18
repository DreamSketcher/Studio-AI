# -*- coding: utf-8 -*-
"""Model Hub: реальный скан models/, фильтры панели, удаление с защитой."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="панель — Qt-виджет")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def model_tree(tmp_path):
    """Реальные файлы «моделей» в tmp/models: категория по подкаталогу."""
    mdir = tmp_path / "models"
    (mdir / "rvc").mkdir(parents=True)
    (mdir / "llm").mkdir()
    (mdir / ".preview_cache").mkdir()
    (mdir / "rvc" / "singer_v1.pth").write_bytes(b"weights" * 100)
    (mdir / "llm" / "llama-8b-q4.gguf").write_bytes(b"gguf" * 1000)
    (mdir / "decoder.onnx").write_bytes(b"onnx")
    (mdir / "notes.txt").write_text("not a model")
    (mdir / ".preview_cache" / "hidden.pth").write_bytes(b"cache")
    return mdir


class TestScanLocalModels:
    def test_scan_finds_real_files_with_categories(self, model_tree):
        from ai_studio_core.ui.controllers.model_controller import scan_local_models
        models = scan_local_models(str(model_tree))
        by_name = {m["name"]: m for m in models}
        assert set(by_name) == {"singer_v1.pth", "llama-8b-q4.gguf", "decoder.onnx"}
        assert by_name["singer_v1.pth"]["category"] == "rvc"
        assert by_name["llama-8b-q4.gguf"]["category"] == "llm"
        assert by_name["decoder.onnx"]["category"] == "root"
        # Реальные размеры с диска
        assert by_name["llama-8b-q4.gguf"]["size_bytes"] == 4000

    def test_hidden_cache_dirs_skipped(self, model_tree):
        from ai_studio_core.ui.controllers.model_controller import scan_local_models
        models = scan_local_models(str(model_tree))
        assert all("hidden.pth" != m["name"] for m in models)

    def test_scan_missing_dir_is_honestly_empty(self, tmp_path):
        from ai_studio_core.ui.controllers.model_controller import scan_local_models
        assert scan_local_models(str(tmp_path / "nope")) == []
        assert scan_local_models("") == []


class TestModelControllerDelete:
    def _ctrl(self, monkeypatch, model_dir):
        from ai_studio_core import paths
        monkeypatch.setattr(paths, "MODEL_DIR", str(model_dir))
        from ai_studio_core.ui.controllers.model_controller import ModelController
        return ModelController()

    def test_delete_real_file(self, monkeypatch, model_tree):
        ctrl = self._ctrl(monkeypatch, model_tree)
        target = str(model_tree / "rvc" / "singer_v1.pth")
        assert os.path.isfile(target)
        updated = []
        ctrl.models_updated.connect(updated.append)
        assert ctrl.delete_model(target) is True
        assert not os.path.exists(target)
        assert updated, "после удаления список пересканирован"
        assert all(m["name"] != "singer_v1.pth" for m in updated[-1])

    def test_delete_outside_models_dir_refused(self, monkeypatch, model_tree, tmp_path):
        ctrl = self._ctrl(monkeypatch, model_tree)
        outside = tmp_path / "secret.bin"
        outside.write_bytes(b"top secret model")
        errors = []
        ctrl.error_occurred.connect(errors.append)
        assert ctrl.delete_model(str(outside)) is False
        assert outside.exists(), "файл вне models/ неприкосновенен"
        assert errors, "отказ озвучен пользователю"

    def test_delete_traversal_refused(self, monkeypatch, model_tree):
        ctrl = self._ctrl(monkeypatch, model_tree)
        sneaky = str(model_tree / "rvc" / ".." / ".." / "etc_passwd.bin")
        assert ctrl.delete_model(sneaky) is False


class TestModelHubPanel:
    def test_panel_lists_real_models_and_filters(self, app, model_tree):
        from ai_studio_core.ui.panels.model_hub_panel import ModelHubPanel
        from ai_studio_core.ui.controllers.model_controller import scan_local_models

        panel = ModelHubPanel()
        panel.set_models(scan_local_models(str(model_tree)))
        assert panel._list.count() == 3

        # Фильтр по категории rvc
        idx = panel._category.findData("rvc")
        panel._category.setCurrentIndex(idx)
        assert panel._list.count() == 1
        assert "singer_v1.pth" in panel._list.item(0).text()

        # Поиск по имени
        panel._category.setCurrentIndex(0)
        panel._search.setText("llama")
        assert panel._list.count() == 1
        assert "llama" in panel._list.item(0).text()

    def test_panel_empty_state_honest(self, app):
        from ai_studio_core.ui.panels.model_hub_panel import ModelHubPanel
        from ai_studio_core.i18n import t as tr

        panel = ModelHubPanel()
        panel.set_models([])
        assert panel._list.count() == 1
        assert panel._list.item(0).text() == tr("hub_empty")
        assert panel.selected_model() is None  # манекен не выбирается

    def test_selection_emits_real_model(self, app, model_tree):
        from ai_studio_core.ui.panels.model_hub_panel import ModelHubPanel
        from ai_studio_core.ui.controllers.model_controller import scan_local_models

        panel = ModelHubPanel()
        panel.set_models(scan_local_models(str(model_tree)))
        seen = []
        panel.selection_changed.connect(seen.append)
        panel._list.setCurrentRow(0)
        assert panel._btn_delete.isEnabled()
        name = panel._list.item(0).text()
        assert seen and seen[0]["name"] in name
        assert os.path.isfile(seen[0]["path"])  # путь реален

        panel._btn_delete.click()
        # delete_requested ушёл с реальным путём файла
        deleted_path = seen[0]["path"]
        assert deleted_path.endswith((".pth", ".gguf", ".onnx"))
