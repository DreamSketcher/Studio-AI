"""Точка входа приложения."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QFile, QTextStream, Qt
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme.palette import make_dark_palette


def run() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Studio")
    app.setOrganizationName("ai_studio")
    app.setApplicationVersion("0.1.0")

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
