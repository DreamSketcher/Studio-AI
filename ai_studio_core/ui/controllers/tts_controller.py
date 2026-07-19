"""Контроллер TTS Workspace — реальный синтез через доступные бэкенды.

Бэкенды (по приоритету):
  1. coqui   — torch + TTS (XTTS v2), если extras .[ml] установлены;
  2. espeak  — системный espeak-ng/espeak (реальный WAV без ML-зависимостей).

Если ни один недоступен — пользователь получает честную ошибку,
файла-пустышки не создаётся. RVC пока не имеет бэкенда в этой сборке —
при включённом RVC генерация останавливается с явной ошибкой заранее.
"""
from __future__ import annotations

import os
import wave
from types import SimpleNamespace

from PySide6.QtCore import Signal, Slot

from ai_studio_core.i18n import t as tr

from .base_controller import BaseController

CHUNK_SILENCE_MS = 150  # пауза между склеенными чанками


def _coqui_available() -> bool:
    try:
        import torch  # noqa: F401
        import TTS    # noqa: F401
        return True
    except Exception:
        return False


def _detect_backend() -> str | None:
    from ai_studio_core import espeak_tts
    if _coqui_available():
        return "coqui"
    if espeak_tts.available():
        return "espeak"
    return None


def _concat_wavs(paths: list[str], out_path: str, silence_ms: int = CHUNK_SILENCE_MS) -> None:
    """Склеивает WAV-чанки (одинаковых параметров) в один файл с паузами."""
    if not paths:
        raise ValueError("nothing to concat")
    frames_all: list[bytes] = []
    params = None
    silence_b = b""
    for i, p in enumerate(paths):
        with wave.open(p, "rb") as wf:
            cp = wf.getparams()
            if params is None:
                params = cp
                silence_frames = int(cp.framerate * silence_ms / 1000)
                silence_b = b"\x00" * silence_frames * cp.sampwidth * cp.nchannels
            elif (cp.nchannels, cp.sampwidth, cp.framerate) != (
                params.nchannels, params.sampwidth, params.framerate
            ):
                raise ValueError(f"chunk {p} has different wav params")
            frames_all.append(wf.readframes(wf.getnframes()))
            if i < len(paths) - 1:
                frames_all.append(silence_b)

    with wave.open(out_path, "wb") as out:
        out.setparams(params)
        out.writeframes(b"".join(frames_all))


class TTSController(BaseController):
    # Сигналы для UI
    generation_started = Signal()
    generation_progress = Signal(int, str)
    generation_complete = Signal(str)      # путь к итоговому аудио
    pipeline_step_changed = Signal(int, str)
    backend_changed = Signal(str)          # "coqui" | "espeak"

    def __init__(self):
        super().__init__()
        self._normalize_fn = None
        self._chunk_fn = None
        self._backend: str | None = None
        self._preferred_backend = "auto"  # auto | coqui | espeak
        self._queue = None          # QueueController (attach_queue)
        self._task_id: str | None = None
        self._last_output: str | None = None

    # ── Публичное API ──

    def backend(self) -> str | None:
        return self._backend

    def preferred_backend(self) -> str:
        return self._preferred_backend

    def last_output(self) -> str | None:
        return self._last_output

    def available_models(self) -> list[dict]:
        """Реальные TTS-движки для селектора: статус отражает фактическую
        доступность в текущем окружении (без обещаний несуществующего)."""
        from ai_studio_core import espeak_tts
        pref = self._preferred_backend
        return [
            {"id": "auto", "name": tr("model_auto"), "provider": "",
             "status": "ready", "current": pref == "auto"},
            {"id": "coqui", "name": "Coqui XTTS v2", "provider": tr("prov_engines"),
             "status": "ready" if _coqui_available() else "download",
             "current": pref == "coqui"},
            {"id": "espeak", "name": "espeak-ng", "provider": tr("prov_engines"),
             "status": "ready" if espeak_tts.available() else "error",
             "current": pref == "espeak"},
        ]

    @Slot(str)
    def select_backend(self, backend_id: str) -> None:
        """Фиксирует выбранный движок; 'auto' — автоопределение (coqui→espeak)."""
        bid = (backend_id or "").strip() or "auto"
        if bid not in ("auto", "coqui", "espeak"):
            self.log_message.emit("WARN", f"unknown TTS backend: {backend_id}")
            return
        self._preferred_backend = bid
        self._backend = None  # пересчитается при следующей генерации
        self.status_message.emit(f"TTS backend: {bid}")

    def rvc_models(self) -> list[dict]:
        """Реальный скан каталога моделей на .pth-файлы RVC.

        Ничего не найдено — честно пустой список (RVC-гейт в on_generate
        всё равно не пропустит конвертацию без бэкенда)."""
        import glob
        out: list[dict] = []
        try:
            from ai_studio_core.paths import MODEL_DIR
            if os.path.isdir(MODEL_DIR):
                for p in sorted(glob.glob(os.path.join(MODEL_DIR, "**", "*.pth"),
                                          recursive=True)):
                    out.append({"id": p, "name": os.path.basename(p),
                                "provider": "RVC", "status": "ready"})
        except Exception as e:
            self.log_message.emit("WARN", f"RVC model scan failed: {e}")
        return out

    def attach_queue(self, queue_controller) -> None:
        """Подключает очередь задач: генерация регистрирует в ней реальную задачу."""
        self._queue = queue_controller

    def export_last(self, target_path: str) -> str:
        """Конвертирует/копирует последний результат в target_path (формат — по расширению)."""
        if not self._last_output or not os.path.exists(self._last_output):
            raise RuntimeError("no generated audio to export")
        src_ext = os.path.splitext(self._last_output)[1].lower()
        dst_ext = os.path.splitext(target_path)[1].lower().lstrip(".")
        if not dst_ext:
            raise ValueError("target has no extension")
        if f".{dst_ext}" == src_ext:
            import shutil
            shutil.copyfile(self._last_output, target_path)
            return target_path
        return self._convert(self._last_output, target_path, dst_ext)

    # ── Внутренняя подготовка ──

    def _ensure_engine(self) -> bool:
        if self._normalize_fn is not None and self._chunk_fn is not None:
            return True
        try:
            from ai_studio_core.normalizer import TextNormalizer
            from ai_studio_core.chunker import TextChunker
            self._normalize_fn = TextNormalizer().normalize
            self._chunk_fn = TextChunker().chunk_text
            self.log_message.emit("INFO", tr("ctl_engine_loaded"))
            return True
        except Exception as e:
            self.log_message.emit("WARN", f"TTS engine deps unavailable: {e}")
            return False

    def _ensure_backend(self) -> bool:
        if self._backend is None:
            self._backend = self._resolve_backend()
            if self._backend:
                self.backend_changed.emit(self._backend)
                self.log_message.emit("INFO", f"TTS backend: {self._backend}")
        return self._backend is not None

    def _resolve_backend(self) -> str | None:
        """Уважает выбор пользователя: закреплённый движок проверяется честно,
        авто — coqui→espeak по факту доступности."""
        if self._preferred_backend == "coqui":
            return "coqui" if _coqui_available() else None
        if self._preferred_backend == "espeak":
            from ai_studio_core import espeak_tts
            return "espeak" if espeak_tts.available() else None
        return _detect_backend()

    # ── Генерация ──

    @Slot(str, dict)
    def on_generate(self, text: str, params: dict) -> None:
        engine_ok = self._ensure_engine()
        backend_ok = self._ensure_backend()

        if not engine_ok or not backend_ok:
            self.pipeline_step_changed.emit(0, "error")
            if backend_ok is False and self._preferred_backend not in ("", "auto"):
                # Пользователь явно выбрал движок — говорим именно про него
                msg = f'{tr("ctl_backend_missing")}: {self._preferred_backend}'
            else:
                msg = tr("ctl_tts_missing")
            self.error_occurred.emit(msg)
            self.status_message.emit(msg)
            return

        if params.get("rvc_enabled"):
            # Честный гейт: RVC-бэкенда в сборке нет — не выдаём синтез за конвертацию.
            self.pipeline_step_changed.emit(3, "error")
            self.error_occurred.emit(tr("ctl_rvc_missing"))
            self.log_message.emit("WARN", tr("ctl_rvc_missing"))
            return

        self.generation_started.emit()
        if self._queue is not None:
            self._task_id = self._queue.add_task(
                "TTS", self._backend or "?", {"language": params.get("language", "auto")}
            )
        worker = self._run_in_background(self._generate_impl, text=text, params=params)
        worker.progress.connect(self.generation_progress.emit)
        worker.progress.connect(self._on_worker_progress)
        worker.result.connect(self._on_done)
        worker.error.connect(self._on_impl_error)

    def _on_worker_progress(self, pct: int, _status: str) -> None:
        if self._queue is not None and self._task_id:
            self._queue.set_task_progress(self._task_id, int(pct), "running")

    def _generate_impl(self, text: str, params: dict,
                       progress_callback=None, cancel_check=None) -> str:
        # Выходной каталог должен существовать до записи волн
        try:
            from ai_studio_core.paths import OUTPUT_DIR
            os.makedirs(OUTPUT_DIR, exist_ok=True)
        except Exception:
            pass

        # 1. Normalize
        if progress_callback:
            progress_callback(10, "Normalizing…")
        self.pipeline_step_changed.emit(0, "done")
        self.pipeline_step_changed.emit(1, "active")
        normalized = self._normalize_fn(text) if self._normalize_fn else text
        if cancel_check and cancel_check():
            return self._aborted()
        self.pipeline_step_changed.emit(1, "done")

        # 2. Chunk
        if progress_callback:
            progress_callback(20, "Chunking…")
        self.pipeline_step_changed.emit(2, "active")
        chunks = self._chunk_fn(normalized) if self._chunk_fn else [normalized]
        chunks = [c for c in chunks if c and c.strip()] or [normalized]
        if cancel_check and cancel_check():
            return self._aborted()

        # 3. Synthesis per chunk (реальный бэкенд)
        if self._backend == "coqui":
            wav_path = self._synthesize_coqui(chunks, params, progress_callback, cancel_check)
        else:
            wav_path = self._synthesize_espeak(chunks, params, progress_callback, cancel_check)
        if not wav_path:  # отменено
            return self._aborted()
        self.pipeline_step_changed.emit(2, "done")

        # 4. RVC (в эту точку не дойдём при включённом RVC — гейт на входе)
        self.pipeline_step_changed.emit(3, "done")

        # 5. Output: конвертация формата при необходимости
        self.pipeline_step_changed.emit(5, "active")
        if progress_callback:
            progress_callback(95, "Finalizing…")
        final_path = self._apply_output_format(wav_path, params)
        if progress_callback:
            progress_callback(100, "Done")
        self.pipeline_step_changed.emit(4, "done")
        self.pipeline_step_changed.emit(5, "done")
        return final_path

    def _synthesize_espeak(self, chunks, params, progress_callback, cancel_check) -> str:
        from ai_studio_core import espeak_tts
        from ai_studio_core.output_naming import _make_output_name

        if params.get("reference_audio"):
            self.log_message.emit(
                "WARN", "espeak backend: reference audio is not supported "
                "(voice cloning requires Coqui XTTS backend) — using default voice"
            )
        part_paths: list[str] = []
        try:
            for i, chunk in enumerate(chunks):
                if cancel_check and cancel_check():
                    return ""
                res = espeak_tts.synthesize(
                    chunk,
                    language=params.get("language", "auto"),
                    speed=params.get("speed", 1.0),
                )
                part_paths.append(res.path)
                pct = 20 + int(70 * (i + 1) / len(chunks))
                if progress_callback:
                    progress_callback(pct, f"Synthesizing {i + 1}/{len(chunks)}…")
            out_path = _make_output_name(chunks[0])
            if len(part_paths) == 1:
                import shutil
                shutil.move(part_paths[0], out_path)
            else:
                _concat_wavs(part_paths, out_path)
            return out_path
        finally:
            for p in part_paths:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass

    def _synthesize_coqui(self, chunks, params, progress_callback, cancel_check) -> str:
        """Coqui XTTS v2 — задействуется только когда extras .[ml] установлены."""
        import torch
        from TTS.api import TTS
        from ai_studio_core.output_naming import _make_output_name

        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        part_paths: list[str] = []
        import tempfile
        ref = params.get("reference_audio") or None
        if not ref:
            raise RuntimeError(
                "Coqui XTTS requires a reference audio file for voice cloning. "
                "Drop a .wav into the reference zone or use the espeak backend."
            )
        lang = params.get("language", "auto")
        lang = "en" if lang == "auto" else lang
        for i, chunk in enumerate(chunks):
            if cancel_check and cancel_check():
                return ""
            fd, part = tempfile.mkstemp(suffix=".wav", prefix="xtts_")
            os.close(fd)
            tts.tts_to_file(text=chunk, speaker_wav=ref, language=lang, file_path=part)
            part_paths.append(part)
            if progress_callback:
                progress_callback(20 + int(70 * (i + 1) / len(chunks)),
                                  f"Synthesizing {i + 1}/{len(chunks)}…")
        out_path = _make_output_name(chunks[0])
        if len(part_paths) == 1:
            import shutil
            shutil.move(part_paths[0], out_path)
        else:
            _concat_wavs(part_paths, out_path)
        return out_path

    def _apply_output_format(self, wav_path: str, params: dict) -> str:
        out_format = str(params.get("output_format", "wav")).lower()
        if out_format in ("", "wav"):
            return wav_path
        target = os.path.splitext(wav_path)[0] + f".{out_format}"
        converted = self._convert(wav_path, target, out_format)
        try:
            os.remove(wav_path)
        except OSError:
            pass
        return converted

    def _convert(self, src: str, dst: str, fmt: str) -> str:
        """Реальная конвертация через pydub+ffmpeg; честная ошибка при недоступности."""
        try:
            from pydub import AudioSegment
        except ImportError as e:
            raise RuntimeError(
                "Audio conversion requires pydub+ffmpeg. "
                "Install ffmpeg or keep WAV as output format."
            ) from e
        audio = AudioSegment.from_wav(src)
        audio.export(dst, format=fmt)
        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            raise RuntimeError(f"conversion to {fmt} produced empty file")
        return dst

    def _aborted(self) -> str:
        if self._queue is not None and self._task_id:
            self._queue.set_task_progress(self._task_id, 0, "cancelled")
        self.status_message.emit(tr("ctl_gen_cancelled"))
        return ""

    def _on_done(self, output_path: str) -> None:
        if not output_path:
            return
        self._last_output = output_path
        if self._queue is not None and self._task_id:
            self._queue.set_task_progress(self._task_id, 100, "done")
        self._record_history(output_path)
        self.generation_complete.emit(output_path)
        self.status_message.emit(f'{tr("msg_generation_complete")}: {output_path}')
        self.log_message.emit("INFO", f"Generated: {output_path}")

    def _on_impl_error(self, message: str) -> None:
        if self._queue is not None and self._task_id:
            self._queue.set_task_progress(self._task_id, 0, "error")

    def _record_history(self, output_path: str) -> None:
        try:
            from ai_studio_core.history_store import save_history
            from ai_studio_core.espeak_tts import wav_info
            try:
                _frames, _rate, duration = wav_info(output_path)
            except Exception:
                duration = 0.0
            task = SimpleNamespace(
                text=os.path.basename(output_path),
                voice=self._backend or "",
                quality="",
                output_path=output_path,
                stats={"time_sec": round(duration, 2), "chunks": 0},
            )
            save_history(task)
        except Exception as e:
            self.log_message.emit("WARN", f"history record failed: {e}")

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit(tr("ctl_gen_cancelled"))
        self.log_message.emit("INFO", tr("ctl_gen_cancelled"))
