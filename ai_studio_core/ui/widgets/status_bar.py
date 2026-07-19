"""Статус-бар с мониторингом ресурсов (GPU, VRAM, CPU, RAM, Queue).

Честность показателей:
  * CPU/RAM — psutil (реальные, раз в 2 с);
  * GPU/VRAM — только если диагностика подтвердила рабочий torch+CUDA;
               сам torch импортируется ЛЕНИВО, при первой удачной пробе,
               в методе _ensure_torch_probe() и только в момент таймера
               (НЕ на конструкторе и не на старте окна). Если импорт упал —
               индикаторы остаются в «—» и больше не пытаются до следующего
               процесса; это не мешает запуску GUI.
  * Queue — реальное число задач из QueueController (set_queue_size).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from ..diag_bridge import get_bridge
from ..theme.tokens import TOKENS


class ResourceStatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QStatusBar {{ background: {TOKENS.colors.bg_secondary}; "
            f"color: {TOKENS.colors.text_secondary}; "
            f"border-top: 1px solid {TOKENS.colors.border_default}; "
            f"font-size: {TOKENS.font_size.caption}px; }}"
            f"QStatusBar::item {{ border: none; }}"
        )

        self._message_label = QLabel("Ready")
        self._message_label.setStyleSheet("border: none; padding: 0 4px;")
        self.addWidget(self._message_label, 1)

        self._gpu_label = self._make_indicator("GPU: —")
        self._vram_label = self._make_indicator("VRAM: — / —")
        self._cpu_label = self._make_indicator("CPU: —")
        self._ram_label = self._make_indicator("RAM: —")
        self._queue_label = self._make_indicator("Queue: 0")

        for w in (self._gpu_label, self._vram_label, self._cpu_label,
                  self._ram_label, self._queue_label):
            self.addPermanentWidget(w)

        # Торч импортируем ЛЕНИВО и только после подтверждения, что он
        # рабочий (через кэш диагностики). Пока флаг _torch_loaded = False —
        # даже и не пытаемся дёргать нативные библиотеки на таймере.
        self._torch = None
        self._torch_load_attempted = False
        self._torch_load_failed = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_resources)
        self._poll_timer.start()

        # Подписываемся на обновление диагностики — когда в фоне
        # подтвердится наличие CUDA, статус‑бар начнёт показывать GPU/VRAM.
        try:
            get_bridge().diagnostics_updated.connect(self._on_diag_updated)
            get_bridge().cuda_info_changed.connect(self._on_cuda_info_changed)
        except Exception:
            pass

    def stop_polling(self) -> None:
        """Остановить периодический опрос psutil/GPU (AI_STUDIO_NO_PS=1,
        отладочный выключатель для изоляции нативных падений на старте)."""
        try:
            self._poll_timer.stop()
        except Exception:
            pass

    def set_message(self, text: str) -> None:
        self._message_label.setText(text)

    def set_queue_size(self, count: int) -> None:
        self._queue_label.setText(f"Queue: {int(count)}")

    def update_stats(
        self,
        gpu_percent: int | None = None,
        vram_used_gb: float | None = None,
        vram_total_gb: float | None = None,
        cpu_percent: int | None = None,
        queue_size: int | None = None,
    ) -> None:
        if gpu_percent is not None:
            color = self._utilization_color(gpu_percent)
            self._gpu_label.setText(f"GPU: {gpu_percent}%")
            self._gpu_label.setStyleSheet(f"color: {color}; border: none; padding: 0 8px;")
        if vram_used_gb is not None and vram_total_gb is not None:
            pct = vram_used_gb / vram_total_gb * 100 if vram_total_gb > 0 else 0
            color = self._utilization_color(int(pct))
            self._vram_label.setText(f"VRAM: {vram_used_gb:.1f}/{vram_total_gb:.1f} GB")
            self._vram_label.setStyleSheet(f"color: {color}; border: none; padding: 0 8px;")
        if cpu_percent is not None:
            self._cpu_label.setText(f"CPU: {cpu_percent}%")
        if queue_size is not None:
            self.set_queue_size(queue_size)

    @staticmethod
    def _make_indicator(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"border: none; padding: 0 8px;")
        return label

    @staticmethod
    def _utilization_color(percent: int) -> str:
        if percent < 60:
            return TOKENS.colors.accent_success
        elif percent < 85:
            return TOKENS.colors.accent_warning
        return TOKENS.colors.accent_error

    def _on_diag_updated(self) -> None:
        """Сбросить флаг неудачной попытки после того как кэш обновился."""
        self._torch_load_attempted = False
        self._torch_load_failed = False

    def _on_cuda_info_changed(self, available: bool, _name: str) -> None:
        if not available:
            # CUDA нет — явно сбрасываем индикаторы на «—»
            self._gpu_label.setText("GPU: —")
            self._vram_label.setText("VRAM: — / —")

    def _ensure_torch(self):
        """Ленивый импорт torch в момент _poll_resources (т.е. на таймере,
        ПОСЛЕ того как окно уже показано и диагностика успела подтвердить,
        что torch рабочий). Даже если импорт упадёт — это произойдёт в
        основном цикле событий в обработчике таймера, а не в __init__,
        и будет поймано в try/except ниже; индикаторы просто останутся «—».
        """
        if self._torch is not None:
            return self._torch
        if self._torch_load_failed:
            return None
        if self._torch_load_attempted:
            return None
        # Прежде чем тянуть нативный torch в этом процессе, проверяем,
        # что диагностика посчитала его рабочим. Если в кэше torch ещё не
        # подтверждён — не рискуем, ждём.
        try:
            if not get_bridge().component_ok("torch"):
                return None
        except Exception:
            return None
        self._torch_load_attempted = True
        try:
            import torch  # noqa: F811 — умышленно ленивый импорт
            self._torch = torch
            return torch
        except Exception:
            self._torch_load_failed = True
            return None

    def _poll_resources(self) -> None:
        """Опрос CPU/RAM раз в 2 с. GPU/VRAM — только если torch+CUDA реально есть,
        и только ПОСЛЕ того как диагностика подтвердила рабочий torch в фоне."""
        try:
            import psutil
            self._cpu_label.setText(f"CPU: {psutil.cpu_percent(interval=None):.0f}%")
            mem = psutil.virtual_memory()
            self._ram_label.setText(f"RAM: {mem.percent:.0f}%")
        except Exception:
            pass

        torch = self._ensure_torch()
        if torch is None:
            return
        try:
            if not torch.cuda.is_available():
                return
            dev = torch.cuda.current_device()
            used = torch.cuda.memory_allocated(dev) / 1024**3
            total = torch.cuda.get_device_properties(dev).total_memory / 1024**3
            pct = int(used / total * 100) if total > 0 else 0
            color = self._utilization_color(pct)
            self._gpu_label.setText(f"GPU: {pct}%")
            self._gpu_label.setStyleSheet(f"color: {color}; border: none; padding: 0 8px;")
            self._vram_label.setText(f"VRAM: {used:.1f}/{total:.1f} GB")
            self._vram_label.setStyleSheet(f"color: {color}; border: none; padding: 0 8px;")
        except Exception:
            pass
