"""Тема оформления: токены, палитра, QSS."""
from .tokens import TOKENS, DARK, ColorScheme, Spacing, Radius, FontSize, Duration
from .palette import make_dark_palette

__all__ = ["TOKENS", "DARK", "make_dark_palette"]
