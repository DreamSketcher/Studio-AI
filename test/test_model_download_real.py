# -*- coding: utf-8 -*-
"""Реальное скачивание модели: loopback HTTP-сервер отдаёт .pth,
rvc_catalog.downloader кладёт файл в models/rvc (подменённый на tmp),
контроллер эмитит честные сигналы прогресса/завершения.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ai_studio_core import paths

pytest.importorskip("PySide6", reason="контроллер — QObject")

from PySide6.QtWidgets import QApplication

PAYLOAD = b"FAKE-RVC-WEIGHTS-" + bytes(range(256)) * 16  # ~4.3 KB «весов»


class _FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/voice1.pth"):
            body = PAYLOAD
            self.send_response(200)
        else:
            body = b"nope"
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def file_server():
    server = HTTPServer(("127.0.0.1", 0), _FileHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


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
def rvc_dir(tmp_path, monkeypatch):
    """Перенаправляем models/rvc в tmp — репозиторий не мусорим.

    metadata.py читает `_C.RVC_METADATA_DIR` напрямую из _constants
    (минуя алиас пакета) — перенаправляем оба пути.
    """
    import ai_studio_core.rvc_catalog as pkg
    from ai_studio_core.rvc_catalog import _constants as C
    d = tmp_path / "models" / "rvc"
    monkeypatch.setattr(pkg, "RVC_MODELS_DIR", str(d))
    monkeypatch.setattr(C, "RVC_METADATA_DIR", str(d / ".metadata"))
    return d


class TestDownloaderCore:
    def test_real_http_download_bytes_exact(self, file_server, rvc_dir):
        from ai_studio_core.rvc_catalog.downloader import (
            download_model, is_downloaded, local_model_path,
        )
        port = file_server.server_address[1]
        entry = {"id": "t1", "name": "Loop Voice",
                 "url": f"http://127.0.0.1:{port}/voice1.pth"}

        progress = []
        ok = download_model(entry, progress_callback=lambda d, t: progress.append((d, t)))
        assert ok is True
        path = local_model_path(entry)
        assert path.startswith(str(rvc_dir))
        with open(path, "rb") as f:
            assert f.read() == PAYLOAD  # побайтово тот же файл
        assert is_downloaded(entry) is True
        assert progress, "прогресс-отчёты были"

    def test_sha256_verified(self, file_server, rvc_dir):
        from ai_studio_core.rvc_catalog.downloader import download_model
        port = file_server.server_address[1]
        good = hashlib.sha256(PAYLOAD).hexdigest()
        entry = {"id": "t2", "name": "Hashed",
                 "url": f"http://127.0.0.1:{port}/voice1.pth", "sha256": good}
        assert download_model(entry) is True

    def test_sha256_mismatch_rejected(self, file_server, rvc_dir):
        from ai_studio_core.rvc_catalog.downloader import download_model, local_model_path
        port = file_server.server_address[1]
        entry = {"id": "t3", "name": "Tampered",
                 "url": f"http://127.0.0.1:{port}/voice1.pth", "sha256": "0" * 64}
        assert download_model(entry) is False
        assert not os.path.exists(local_model_path(entry))

    def test_server_404_fails_honestly(self, file_server, rvc_dir):
        from ai_studio_core.rvc_catalog.downloader import download_model
        port = file_server.server_address[1]
        entry = {"id": "t4", "name": "Missing",
                 "url": f"http://127.0.0.1:{port}/nope.pth"}
        assert download_model(entry) is False
        assert list(rvc_dir.glob("*.pth")) == []


class TestModelControllerDownload:
    def test_download_entry_end_to_end(self, app, file_server, rvc_dir, monkeypatch):
        from ai_studio_core.ui.controllers.model_controller import ModelController
        # refresh() сканирует paths.MODEL_DIR — направляем в тот же tmp
        monkeypatch.setattr(paths, "MODEL_DIR", str(rvc_dir.parent))

        ctrl = ModelController()
        port = file_server.server_address[1]
        entry = {"id": "t5", "name": "Ctrl Voice",
                 "url": f"http://127.0.0.1:{port}/voice1.pth"}

        started, progressed, finished, failed, updated = [], [], [], [], []
        ctrl.download_started.connect(started.append)
        ctrl.download_progress.connect(lambda n, p: progressed.append(p))
        ctrl.download_finished.connect(finished.append)
        ctrl.download_failed.connect(lambda n, m: failed.append((n, m)))
        ctrl.models_updated.connect(updated.append)

        ctrl.download_entry(entry)
        assert _wait(app, lambda: bool(finished) or bool(failed), 30)
        assert finished == ["Ctrl Voice"], f"failed={failed}"
        assert progressed and progressed[-1] == 100
        assert started == ["Ctrl Voice"]

        # файлы на диске и в обновлённом скане
        assert (rvc_dir / "voice1.pth").read_bytes() == PAYLOAD
        assert updated, "скан обновился после скачивания"
        names = [m["name"] for m in updated[-1]]
        assert "voice1.pth" in names
        assert ctrl.is_downloaded(entry) is True

    def test_download_failure_signal_honest(self, app, file_server, rvc_dir):
        from ai_studio_core.ui.controllers.model_controller import ModelController

        ctrl = ModelController()
        port = file_server.server_address[1]
        entry = {"id": "t6", "name": "Broken Voice",
                 "url": f"http://127.0.0.1:{port}/missing.pth"}
        finished, failed = [], []
        ctrl.download_finished.connect(finished.append)
        ctrl.download_failed.connect(lambda n, m: failed.append((n, m)))
        ctrl.download_entry(entry)
        assert _wait(app, lambda: bool(finished) or bool(failed), 30)
        assert not finished
        assert failed and failed[0][0] == "Broken Voice"
