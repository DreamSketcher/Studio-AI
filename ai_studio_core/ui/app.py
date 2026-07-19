"""Точка входа приложения."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QFile, QSettings, QTextStream, Qt
from PySide6.QtWidgets import QApplication

from ai_studio_core import i18n

from .main_window import MainWindow
from .theme.palette import make_dark_palette

_LANGUAGE_KEY = "ui/language"


def run() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Studio")
    app.setOrganizationName("ai_studio")
    app.setApplicationVersion("0.1.0")

    # Язык интерфейса восстанавливаем до построения виджетов
    saved_lang = QSettings("ai_studio", "studio").value(_LANGUAGE_KEY, None)
    if saved_lang:
        i18n.set_language(str(saved_lang))

    # Тема
    app.setPalette(make_dark_palette())
    _load_stylesheet(app)

    window = MainWindow()
    window.show()

    return app.exec()


def _load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "theme" / "stylesheet.qss"
    if qss_path.exists():
        qf = QFile(str(qss_path))
        if qf.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(qf)
            app.setStyleSheet(stream.readAll())
            qf.close()


if __name__ == "__main__":
    sys.exit(run())
