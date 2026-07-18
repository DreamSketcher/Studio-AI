"""Environment setup wizard — каркас мастера первоначальной настройки."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout, QWizard, QWizardPage,
)

from ..theme.tokens import TOKENS


class EnvSetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Studio — First Setup")
        self.setMinimumSize(560, 420)

        self.addPage(IntroPage())
        self.addPage(ComponentsPage())
        self.addPage(ProgressPage())
        self.addPage(FinishPage())


class IntroPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome")
        l = QVBoxLayout(self)
        l.addWidget(QLabel(
            "Этот мастер поможет настроить AI Studio:\n"
            "• выбрать каталоги для моделей и вывода\n"
            "• установить необходимые ML-компоненты (torch, TTS, RVC)\n"
            "• проверить систему (CUDA, ffmpeg, кодеки)\n\n"
            "Для работы базового GUI достаточно нажать «Далее» и пропустить "
            "скачивание больших моделей — их можно установить позже через "
            "вкладку «Окружение»."
        ))


class ComponentsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Components")
        l = QVBoxLayout(self)
        self.chk_torch = QCheckBox("Install torch (required for TTS/RVC/LLM)")
        self.chk_torch.setChecked(True)
        self.chk_tts = QCheckBox("Install Coqui TTS")
        self.chk_tts.setChecked(True)
        self.chk_rvc = QCheckBox("Install RVC support")
        self.chk_ffmpeg = QCheckBox("Verify ffmpeg")
        self.chk_ffmpeg.setChecked(True)
        for c in (self.chk_torch, self.chk_tts, self.chk_rvc, self.chk_ffmpeg):
            l.addWidget(c)
        l.addStretch()


class ProgressPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installing…")
        l = QVBoxLayout(self)
        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        l.addWidget(self._bar)
        l.addWidget(QLabel("(В этой демо-версии мастер не скачивает компоненты — "
                           "реальные установки делаются через панель «Окружение».)"))


class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Ready")
        l = QVBoxLayout(self)
        l.addWidget(QLabel("✅ Настройка завершена.\n\n"
                          "Запустится основной интерфейс AI Studio."))
