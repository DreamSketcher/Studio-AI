"""Контроллер управления моделями (скачивание, удаление, обновление списка)."""
from __future__ import annotations

from PySide6.QtCore import Signal

from .base_controller import BaseController


class ModelController(BaseController):
    models_updated = Signal(list)    # list of dict
    download_started = Signal(str)   # model_id
    download_progress = Signal(str, int, str)  # model_id, percent, status
    download_finished = Signal(str)
    download_failed = Signal(str, str)

    def __init__(self):
        super().__init__()

    def list_models(self) -> list[dict]:
        """Возвращает текущий список моделей (демо)."""
        return [
            {"id": "xtts_v2", "name": "XTTS v2.0.2", "provider": "coqui",
             "status": "ready", "size_mb": 1800},
            {"id": "llama3.1-8b", "name": "Llama 3.1 8B Q4", "provider": "local",
             "status": "download", "size_mb": 4700},
            {"id": "rvc_male1", "name": "RVC Male v2", "provider": "rvc",
             "status": "ready", "size_mb": 420},
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai",
             "status": "ready", "size_mb": 0},
        ]

    def download_model(self, model_id: str) -> None:
        self.log_message.emit("INFO", f"Download requested: {model_id}")
        self.status_message.emit(f"Downloading {model_id}…")
        self.download_started.emit(model_id)
        # Реальная реализация вызывала бы updater/local_llm_client; в демо — таймер.
        self.download_finished.emit(model_id)

    def delete_model(self, model_id: str) -> None:
        self.log_message.emit("INFO", f"Delete requested: {model_id}")
        self.status_message.emit(f"Model deleted: {model_id}")
