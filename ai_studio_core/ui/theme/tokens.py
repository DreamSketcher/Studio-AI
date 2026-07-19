"""
Дизайн-токены — единый источник правды для всех размеров, отступов, цветов.
Меняешь здесь — меняется везде. Никаких магических чисел в виджетах.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor, QFont


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class Radius:
    sm: int = 4
    md: int = 8
    lg: int = 12
    pill: int = 999


@dataclass(frozen=True)
class FontSize:
    caption: int = 11
    body: int = 13
    subtitle: int = 15
    title: int = 18
    headline: int = 24


@dataclass(frozen=True)
class Duration:
    """Длительности анимаций в миллисекундах."""
    fast: int = 150
    normal: int = 250
    slow: int = 400


@dataclass(frozen=True)
class ColorScheme:
    # Surfaces
    bg_primary: str = "#1a1a2e"
    bg_secondary: str = "#16213e"
    bg_tertiary: str = "#0f3460"
    bg_elevated: str = "#222244"

    # Text
    text_primary: str = "#e0e0e0"
    text_secondary: str = "#a0a0b0"
    text_disabled: str = "#606070"
    text_on_accent: str = "#ffffff"

    # Accents
    accent_primary: str = "#7c3aed"      # Фиолетовый — основной
    accent_secondary: str = "#06b6d4"    # Циан — вторичный
    accent_success: str = "#10b981"
    accent_warning: str = "#f59e0b"
    accent_error: str = "#ef4444"

    # Borders
    border_default: str = "#2a2a4a"
    border_focus: str = "#7c3aed"

    # Specific
    waveform_cold: str = "#3b82f6"
    waveform_hot: str = "#ef4444"
    pipeline_connector: str = "#7c3aed"


@dataclass(frozen=True)
class Tokens:
    spacing: Spacing = field(default_factory=Spacing)
    radius: Radius = field(default_factory=Radius)
    font_size: FontSize = field(default_factory=FontSize)
    duration: Duration = field(default_factory=Duration)
    colors: ColorScheme = field(default_factory=ColorScheme)


# Глобальный синглтон — импортируется отовсюду
TOKENS = Tokens()
DARK = TOKENS.colors  # Алиас для удобства
