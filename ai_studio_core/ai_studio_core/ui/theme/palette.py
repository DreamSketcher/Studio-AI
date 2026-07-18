"""
Применение дизайн-токенов к QPalette — используется QApplication.setPalette().
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from .tokens import DARK


def make_dark_palette() -> QPalette:
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window, QColor(DARK.bg_primary))
    p.setColor(QPalette.ColorRole.WindowText, QColor(DARK.text_primary))
    p.setColor(QPalette.ColorRole.Base, QColor(DARK.bg_secondary))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(DARK.bg_tertiary))
    p.setColor(QPalette.ColorRole.Text, QColor(DARK.text_primary))
    p.setColor(QPalette.ColorRole.Button, QColor(DARK.bg_elevated))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(DARK.text_primary))
    p.setColor(QPalette.ColorRole.Highlight, QColor(DARK.accent_primary))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(DARK.text_on_accent))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(DARK.bg_elevated))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(DARK.text_primary))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(DARK.text_disabled))
    p.setColor(QPalette.ColorRole.Link, QColor(DARK.accent_secondary))

    # Disabled state
    p.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(DARK.text_disabled),
    )
    p.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(DARK.text_disabled),
    )

    return p
