"""Точка входа приложения."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QSettings, QTextStream, Qt
from PySide6.QtWidgets import QApplication

from ai_studio_core import i18n
from ai_studio_core.logging_utils import write_log

from .main_window import MainWindow
from .theme.palette import make_dark_palette

_LANGUAGE_KEY = "ui/language"


def _install_qt_log_handler() -> None:
    """Все предупреждения Qt -> logs/xtts_studio.log.

    Перед нативным падением (шрифты DirectWrite, плагины платформы, WASAPI
    и т.п.) Qt почти всегда печатает warning в консоль — в GUI из консоли
    его не прочитать, поэтому перенаправляем в файл лога.
    """
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    levels = {
        QtMsgType.QtInfoMsg: "QT-INFO",
        QtMsgType.QtDebugMsg: "QT-DEBUG",
        QtMsgType.QtWarningMsg: "QT-WARN",
        QtMsgType.QtCriticalMsg: "QT-CRIT",
        QtMsgType.QtFatalMsg: "QT-FATAL",
    }

    def _handler(mode, _ctx, msg):
        try:
            write_log(f"[{levels.get(mode, 'QT')}] {msg}")
        except Exception:
            pass

    qInstallMessageHandler(_handler)


def run() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Studio")
    app.setOrganizationName("ai_studio")
    app.setApplicationVersion("0.1.0")
    _install_qt_log_handler()
    write_log("[GUI] QApplication создан")

    # Язык интерфейса восстанавливаем до построения виджетов
    saved_lang = QSettings("ai_studio", "studio").value(_LANGUAGE_KEY, None)
    if saved_lang:
        i18n.set_language(str(saved_lang))

    # Тема (AI_STUDIO_NO_QSS=1 — отладочный выключатель: без палитры и QSS)
    if os.environ.get("AI_STUDIO_NO_QSS") == "1":
        write_log("[GUI] тема отключена (AI_STUDIO_NO_QSS=1)")
    else:
        app.setPalette(make_dark_palette())
        _load_stylesheet(app)
        write_log("[GUI] палитра и stylesheet применены")

    window = MainWindow()
    write_log("[GUI] MainWindow построено")
    window.show()
    write_log("[GUI] window.show() — вход в exec")
    rc = app.exec()
    write_log(f"[GUI] exec завершён с кодом {rc}")
    return rc


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
