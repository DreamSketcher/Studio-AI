"""Статус-бар с мониторингом ресурсов (GPU, VRAM, CPU, Queue)."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

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
        self._queue_label = self._make_indicator("Queue: 0")

        for w in (self._gpu_label, self._vram_label, self._cpu_label, self._queue_label):
            self.addPermanentWidget(w)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_resources)
        self._poll_timer.start()

    def set_message(self, text: str) -> None:
        self._message_label.setText(text)

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
            self._queue_label.setText(f"Queue: {queue_size}")

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

    def _poll_resources(self) -> None:
        """Опрос CPU/памяти раз в 2с. GPU/VRAM опрашиваются только если torch есть."""
        try:
            import psutil
            self._cpu_label.setText(f"CPU: {psutil.cpu_percent(interval=None):.0f}%")
            mem = psutil.virtual_memory()
            self._queue_label.setText(f"RAM: {mem.percent:.0f}%")
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
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
