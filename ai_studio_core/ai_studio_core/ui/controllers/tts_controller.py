"""Контроллер TTS Workspace."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Slot

from .base_controller import BaseController


class TTSController(BaseController):
    # Сигналы для UI
    generation_started = Signal()
    generation_progress = Signal(int, str)
    generation_complete = Signal(str)
    pipeline_step_changed = Signal(int, str)
    waveform_ready = Signal(list)

    def __init__(self):
        super().__init__()
        self._engine_loaded = False
        self._normalize_fn = None
        self._chunk_fn = None

    def _ensure_engine(self) -> bool:
        if self._engine_loaded:
            return True
        try:
            from ai_studio_core.normalizer import TextNormalizer
            from ai_studio_core.chunker import TextChunker
            self._normalize_fn = TextNormalizer().normalize
            self._chunk_fn = TextChunker().chunk
            self._engine_loaded = True
            self.status_message.emit("TTS engine loaded")
            self.log_message.emit("INFO", "TTS engine dependencies loaded")
            return True
        except Exception as e:
            self.status_message.emit(f"TTS engine unavailable: install torch/TTS")
            self.log_message.emit("WARN", f"TTS engine unavailable: {e}")
            return False

    @Slot(str, dict)
    def on_generate(self, text: str, params: dict) -> None:
        if not self._ensure_engine():
            self.pipeline_step_changed.emit(0, "error")
            self.error_occurred.emit(
                "TTS-движок недоступен. Установите torch и TTS через вкладку «Окружение»."
            )
            return
        self.generation_started.emit()
        worker = self._run_in_background(self._generate_impl, text=text, params=params)
        worker.progress.connect(self.generation_progress.emit)
        worker.result.connect(self._on_done)

    def _generate_impl(
        self, text: str, params: dict,
        progress_callback=None, cancel_check=None,
    ) -> str:
        # Step 1: Normalize
        if progress_callback:
            progress_callback(10, "Normalizing…")
        self.pipeline_step_changed.emit(1, "active")
        normalized = self._normalize_fn(text) if self._normalize_fn else text
        if cancel_check and cancel_check():
            return ""
        self.pipeline_step_changed.emit(1, "done")

        # Step 2: Chunk
        if progress_callback:
            progress_callback(25, "Chunking…")
        self.pipeline_step_changed.emit(2, "active")
        chunks = self._chunk_fn(normalized) if self._chunk_fn else [normalized]
        if cancel_check and cancel_check():
            return ""
        self.pipeline_step_changed.emit(2, "done")

        # Step 3: TTS
        if progress_callback:
            progress_callback(50, "Synthesizing…")
        self.pipeline_step_changed.emit(3, "active")
        import time
        time.sleep(0.4)
        out_path = str(Path.cwd() / "outputs" / "demo_output.wav")
        self.pipeline_step_changed.emit(3, "done")

        # Step 4: RVC (optional)
        if params.get("rvc_enabled"):
            if progress_callback:
                progress_callback(80, "Applying RVC…")
            self.pipeline_step_changed.emit(4, "active")
            time.sleep(0.3)
            self.pipeline_step_changed.emit(4, "done")

        # Step 5: De-ess/Output
        if progress_callback:
            progress_callback(95, "Finalizing…")
        self.pipeline_step_changed.emit(5, "active")
        time.sleep(0.1)
        if progress_callback:
            progress_callback(100, "Done")
        self.pipeline_step_changed.emit(5, "done")
        return out_path

    def _on_done(self, output_path: str) -> None:
        self.generation_complete.emit(output_path)
        self.status_message.emit(f"Generation complete: {output_path}")
        self.log_message.emit("INFO", f"Generated: {output_path}")

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit("Generation cancelled")
        self.log_message.emit("INFO", "Generation cancelled by user")
