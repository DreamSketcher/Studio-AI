"""Мастер проверки окружения AI Studio.

Никаких обещаний скачивания: мастер РЕАЛЬНО проверяет отмеченные
компоненты (бинарники в PATH, импортируемость модулей, версии) и показывает
честный результат. Установка больших моделей — отдельный поток
(меню «Модели» / extras .[ml]).
"""
from __future__ import annotations

import shutil
import subprocess

from PySide6.QtWidgets import (
    QCheckBox, QLabel, QPlainTextEdit, QVBoxLayout, QWizard, QWizardPage,
)

from ..theme.tokens import TOKENS


def _check_ffmpeg() -> tuple[bool, str]:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False, "ffmpeg не найден в PATH"
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True,
                             timeout=10)
        first = (out.stdout or out.stderr).splitlines()[0].strip()
        return True, f"{first} — {exe}"
    except Exception as e:
        return False, f"ffmpeg не стартует: {e}"


def _check_espeak() -> tuple[bool, str]:
    try:
        from ai_studio_core import espeak_tts
        exe = espeak_tts.find_espeak()
    except Exception:
        exe = None
    if exe:
        return True, f"espeak найден — {exe}"
    return False, "espeak-ng не найден (apt install espeak-ng)"


def _check_module(module: str, hint: str) -> tuple[bool, str]:
    try:
        mod = __import__(module)
        ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", "")
        return True, f"{module} {ver}".strip()
    except Exception:
        return False, f"{module} не установлен ({hint})"


def _check_cuda() -> tuple[bool, str]:
    try:
        import torch
    except Exception:
        return False, "torch не установлен — CUDA недоступна"
    try:
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return True, f"CUDA доступна: {name}"
        return False, "torch установлен, но CUDA-устройств нет (режим CPU)"
    except Exception as e:
        return False, f"проверка CUDA не удалась: {e}"


# name → (функция проверки, подсказка). Только реально измеримое.
CHECKS = {
    "ffmpeg": (_check_ffmpeg,),
    "espeak-ng": (_check_espeak,),
    "torch": (lambda: _check_module("torch", "pip install torch"),),
    "Coqui TTS": (lambda: _check_module("TTS", "pip install -e \".[ml]\""),),
    "diffusers": (lambda: _check_module("diffusers", "pip install diffusers"),),
    "CUDA": (_check_cuda,),
}


def run_checks(names: list[str]) -> list[tuple[str, bool, str]]:
    """Реальная проверка выбранных компонентов → [(name, ok, detail)]."""
    results = []
    for name in names:
        entry = CHECKS.get(name)
        if not entry:
            continue
        try:
            ok, detail = entry[0]()
        except Exception as e:
            ok, detail = False, f"проверка упала: {e}"
        results.append((name, ok, detail))
    return results


class IntroPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Проверка окружения")
        l = QVBoxLayout(self)
        l.addWidget(QLabel(
            "Этот мастер проверяет, что в системе уже установлено:\n"
            "• бинарники ffmpeg / espeak-ng\n"
            "• ML-модули torch, Coqui TTS, diffusers\n"
            "• доступность CUDA\n\n"
            "Мастер ничего не скачивает и не ставит — только честный статус.\n"
            "Большие модели устанавливаются отдельно: меню «Модели», "
            "extras .[ml] или системный пакетный менеджер."
        ))


class ComponentsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Компоненты для проверки")
        l = QVBoxLayout(self)
        self.chk_ffmpeg = QCheckBox("Проверить ffmpeg")
        self.chk_ffmpeg.setChecked(True)
        self.chk_espeak = QCheckBox("Проверить espeak-ng (TTS-бэкенд)")
        self.chk_espeak.setChecked(True)
        self.chk_torch = QCheckBox("Проверить torch (нужен для TTS/RVC/LLM)")
        self.chk_torch.setChecked(True)
        self.chk_tts = QCheckBox("Проверить Coqui TTS")
        self.chk_tts.setChecked(True)
        self.chk_diffusers = QCheckBox("Проверить diffusers (изображения)")
        self.chk_cuda = QCheckBox("Проверить CUDA")
        self.chk_cuda.setChecked(True)
        for c in (self.chk_ffmpeg, self.chk_espeak, self.chk_torch,
                  self.chk_tts, self.chk_diffusers, self.chk_cuda):
            l.addWidget(c)
        l.addStretch()

    def selected_components(self) -> list[str]:
        out = []
        if self.chk_ffmpeg.isChecked():
            out.append("ffmpeg")
        if self.chk_espeak.isChecked():
            out.append("espeak-ng")
        if self.chk_torch.isChecked():
            out.append("torch")
        if self.chk_tts.isChecked():
            out.append("Coqui TTS")
        if self.chk_diffusers.isChecked():
            out.append("diffusers")
        if self.chk_cuda.isChecked():
            out.append("CUDA")
        return out


class ProgressPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Проверка…")
        l = QVBoxLayout(self)
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            f"background: {TOKENS.colors.bg_primary}; border: 1px solid "
            f"{TOKENS.colors.border_default}; font-family: monospace;"
        )
        l.addWidget(self._output)
        self.results: list[tuple[str, bool, str]] = []

    def initializePage(self) -> None:
        wizard = self.wizard()
        names = wizard._components.selected_components()
        self.results = run_checks(names)
        lines = []
        for name, ok, detail in self.results:
            mark = "✅" if ok else "❌"
            lines.append(f"{mark} {name}: {detail}")
        self._output.setPlainText("\n".join(lines) or "(ничего не выбрано)")


class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Готово")
        l = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        l.addWidget(self._summary)
        l.addStretch()

    def initializePage(self) -> None:
        results = self.wizard()._progress.results
        ok_count = sum(1 for _n, ok, _d in results if ok)
        missing = [n for n, ok, _d in results if not ok]
        text = f"Проверено компонентов: {len(results)}, доступно: {ok_count}.\n"
        if missing:
            text += ("Отсутствуют: " + ", ".join(missing) + ".\n"
                     "Работать можно и без них — недоступные функции "
                     "честно сообщат об этом при вызове.")
        else:
            text += "Всё выбранное установлено. ✅"
        self._summary.setText(text)


class EnvSetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Проверка окружения")
        self.setMinimumWidth(560)
        self._intro = IntroPage()
        self._components = ComponentsPage()
        self._progress = ProgressPage()
        self._finish = FinishPage()
        for page in (self._intro, self._components, self._progress, self._finish):
            self.addPage(page)
