"""Контроллер управления моделями — всё по-настоящему.

  * scan_local_models() — рекурсивный скан MODEL_DIR на файлы моделей;
  * delete_model(path) — реальное удаление, защита от выхода за MODEL_DIR;
  * catalog() — живой каталог RVC (rvc_catalog.sources) — офлайн честно пуст;
  * download_entry(entry) — реальное HTTP-скачивание через
    rvc_catalog.downloader в worker-потоке с прогрессом.

Никаких демо-записей: пустой каталог моделей → пустой список.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Signal, Slot

from ai_studio_core.i18n import t as tr

from .base_controller import BaseController

# Расширения файлов-моделей, которые показывает Hub.
_MODEL_EXTS = {".pth", ".safetensors", ".bin", ".gguf", ".pt", ".onnx", ".ckpt"}
# Скрытые служебные подкаталоги каталога RVC (кэш превью/метаданных).
_SKIP_DIRS = {".preview_cache", ".parameter_preview_cache", ".metadata"}


def scan_local_models(model_dir: str) -> list[dict]:
    """Реальный скан каталога моделей.

    Запись: {"id" (==path), "path", "name", "category", "size_bytes", "mtime"}.
    Категория — имя подкаталога внутри models/ (rvc/…), иначе 'root'.
    """
    out: list[dict] = []
    if not model_dir or not os.path.isdir(model_dir):
        return out
    for root, dirs, files in os.walk(model_dir):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _MODEL_EXTS:
                continue
            path = os.path.join(root, fname)
            try:
                st = os.stat(path)
            except OSError:
                continue
            rel = os.path.relpath(path, model_dir)
            parts = rel.split(os.sep)
            category = parts[0] if len(parts) > 1 else "root"
            out.append({
                "id": path,
                "path": path,
                "name": fname,
                "category": category,
                "size_bytes": st.st_size,
                "mtime": st.st_mtime,
            })
    out.sort(key=lambda m: (m["category"], m["name"].lower()))
    return out


def _is_inside(path: str, directory: str) -> bool:
    """Защита от path traversal: удалять можно только внутри MODEL_DIR."""
    try:
        p = os.path.realpath(path)
        d = os.path.realpath(directory)
    except OSError:
        return False
    return p != d and p.startswith(d + os.sep) and os.path.isfile(p)


class ModelController(BaseController):
    models_updated = Signal(list)    # list of dict (scan_local_models)
    download_started = Signal(str)   # entry name
    download_progress = Signal(str, int)  # entry name, percent
    download_finished = Signal(str)  # entry name
    download_failed = Signal(str, str)  # entry name, reason

    def __init__(self):
        super().__init__()
        self._models: list[dict] = []
        self._cancel_download = False

    # ── Список локальных моделей ──

    def list_models(self) -> list[dict]:
        return list(self._models)

    @Slot()
    def refresh(self) -> None:
        from ai_studio_core.paths import MODEL_DIR
        self._models = scan_local_models(MODEL_DIR)
        self.models_updated.emit(list(self._models))

    # ── Удаление ──

    @Slot(str)
    def delete_model(self, path: str) -> bool:
        """Реальное удаление файла модели. True при успехе."""
        from ai_studio_core.paths import MODEL_DIR
        if not _is_inside(path, MODEL_DIR):
            self.log_message.emit("WARN", f"refuse to delete outside models/: {path}")
            self.error_occurred.emit(f'{tr("hub_delete_fail")}: {path}')
            return False
        try:
            os.remove(path)
        except OSError as e:
            self.log_message.emit("ERROR", f"delete failed: {e}")
            self.error_occurred.emit(f'{tr("hub_delete_fail")}: {e}')
            return False
        self.log_message.emit("INFO", f"deleted {path}")
        self.status_message.emit(f'{tr("hub_deleted")} {os.path.basename(path)}')
        self.refresh()
        return True

    # ── Каталог + скачивание (реальный rvc_catalog) ──

    def catalog(self) -> list[dict]:
        """Живой RVC-каталог (disk-кэш/seed + сеть). Офлайн — может быть пуст."""
        try:
            from ai_studio_core.rvc_catalog import sources
            return sources.get_catalog()
        except Exception as e:
            self.log_message.emit("WARN", f"catalog unavailable: {e}")
            return []

    def is_downloaded(self, entry: dict) -> bool:
        try:
            from ai_studio_core.rvc_catalog.downloader import is_downloaded
            return bool(is_downloaded(entry))
        except Exception:
            return False

    @Slot(dict)
    def download_entry(self, entry: dict) -> None:
        """Реальное скачивание в models/rvc/ в фоновом потоке."""
        name = str(entry.get("name") or entry.get("id") or "?")
        self._cancel_download = False
        self.download_started.emit(name)
        self.status_message.emit(f"⬇ {name}")

        def _work(progress_callback=None, cancel_check=None) -> bool:
            from ai_studio_core.rvc_catalog import downloader

            def _on_bytes(done, total):
                if total:
                    pct = int(done * 100 / total)
                    if progress_callback:
                        progress_callback(pct, name)
                    self.download_progress.emit(name, pct)

            ok = downloader.download_model(
                entry,
                progress_callback=_on_bytes,
                cancelled_flag=lambda: self._cancel_download or (
                    cancel_check() if cancel_check else False),
            )
            if not ok:
                raise RuntimeError(f'{tr("hub_download_fail")}: {name}')
            return ok

        worker = self._run_in_background(_work)
        worker.result.connect(lambda _ok, n=name: self._on_download_done(n))
        worker.error.connect(lambda msg, n=name: self._on_download_failed(n, msg))

    def cancel_download(self) -> None:
        self._cancel_download = True
        self.cancel_current()

    def _on_download_done(self, name: str) -> None:
        self.download_finished.emit(name)
        self.status_message.emit(f'{tr("hub_download_done")} {name}')
        self.log_message.emit("INFO", f"downloaded {name}")
        self.refresh()

    def _on_download_failed(self, name: str, message: str) -> None:
        self.download_failed.emit(name, message)
        self.log_message.emit("ERROR", f"download failed {name}: {message}")
