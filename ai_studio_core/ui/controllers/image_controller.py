"""Контроллер Image Workspace — честная интеграция генерации изображений.

Локальный бэкенд: diffusers + torch (Stable Diffusion). Не установлен —
понятная ошибка `ctl_img_missing`, изображение-пустышка НЕ рисуется.
Фальшивых «сгенерированных» картинок в UI не существует.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Signal, Slot

from ai_studio_core.i18n import t as tr

from ..diag_bridge import diffusers_available as _diffusers_available_from_cache
from .base_controller import BaseController


def _diffusers_available() -> bool:
    """Доступен ли local SD-бэкенд (torch+diffusers)? Проверка по кэшу диагностики.

    Прямой import torch в GUI‑процессе не делаем — битый torch не должен
    валить окно на старте. Факт наличия torch берём из кэша run_full_diagnostics;
    diffusers проверяется лёгким импортом (не тянет нативные бинарники).
    """
    return _diffusers_available_from_cache()


class ImageController(BaseController):
    image_ready = Signal(str)          # путь к сгенерированному файлу
    generation_progress = Signal(int, str)

    def __init__(self):
        super().__init__()
        self._last_image: str | None = None

    def last_image(self) -> str | None:
        return self._last_image

    def available_models(self) -> list[dict]:
        """Реальный статус бэкенда для селектора — без обещаний."""
        ok = _diffusers_available()
        return [{
            "id": "sd-local",
            "name": "Stable Diffusion (diffusers)",
            "provider": "local",
            "status": "ready" if ok else "download",
        }]

    @Slot(str, dict)
    def on_generate(self, prompt: str, params: dict) -> None:
        if not _diffusers_available():
            # Честный гейт: ни силиконовой картинки, ни тишины.
            self.error_occurred.emit(tr("ctl_img_missing"))
            self.status_message.emit(tr("ctl_img_missing"))
            self.log_message.emit("WARN", f"image backend missing; prompt={prompt[:60]!r}")
            return

        def _work(progress_callback=None, cancel_check=None) -> str:
            return self._generate_diffusers(prompt, params,
                                            progress_callback, cancel_check)

        worker = self._run_in_background(_work)
        worker.progress.connect(self.generation_progress.emit)
        worker.result.connect(self._on_done)

    def _generate_diffusers(self, prompt: str, params: dict,
                            progress_callback=None, cancel_check=None) -> str:
        """Локальный Stable Diffusion — задействуется только с extras .[ml]."""
        import torch
        from diffusers import StableDiffusionPipeline

        from ai_studio_core.paths import OUTPUT_DIR
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        model_id = "runwayml/stable-diffusion-v1-5"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
        pipe = pipe.to(device)
        steps = int(params.get("steps", 28))
        cfg = float(params.get("cfg", 7.0))
        seed = int(params.get("seed", -1))
        generator = None
        if seed >= 0:
            generator = torch.Generator(device=device).manual_seed(seed)

        def _cb(_pipe, i, _t, _kw):
            if progress_callback:
                progress_callback(int(100 * (i + 1) / steps), f"Step {i + 1}/{steps}")
            if cancel_check and cancel_check():
                raise InterruptedError("image generation cancelled")

        w, h = (params.get("size") or "1024×1024").replace("x", "×").split("×")
        result = pipe(prompt, num_inference_steps=steps, guidance_scale=cfg,
                      width=int(w), height=int(h), generator=generator,
                      callback=_cb, callback_steps=1)
        from time import strftime
        out_path = os.path.join(OUTPUT_DIR, f"image_{strftime('%Y%m%d_%H%M%S')}.png")
        result.images[0].save(out_path)
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError("image backend produced empty file")
        return out_path

    def _on_done(self, path) -> None:
        if not path:
            return
        self._last_image = path
        self.image_ready.emit(path)
        self.status_message.emit(f"Image: {path}")

    @Slot()
    def on_stop(self) -> None:
        self.cancel_current()
        self.status_message.emit(tr("ctl_gen_cancelled"))
