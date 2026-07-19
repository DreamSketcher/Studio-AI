"""ExperienceManager — исполнитель пресетов поверх событий приложения.

Принцип «честных состояний»: менеджер делает только transient-эффекты
(toast, звук, акцентный пульс с авто-затуханием). Никаких персистентных
изменений интерфейса без явного действия пользователя.

Звук — через QSoundEffect, guarded: без аудио-устройства тихо и без ошибок.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ai_studio_core.i18n import t as tr

from . import sounds

try:  # мультимедиа может отсутствовать в headless-сборке Qt
    from PySide6.QtMultimedia import QSoundEffect
except Exception:  # pragma: no cover
    QSoundEffect = None


class _SafeFormat(dict):
    """format_map: отсутствующие плейсхолдеры остаются как есть, без KeyError."""

    def __missing__(self, key):
        return "{" + key + "}"


def resolve_text(template: str, payload: dict | None = None) -> str:
    """Текст toast'а: i18n-ключ, если такой есть, иначе литерал + {payload}."""
    translated = tr(template)
    text = translated if translated != template else template
    try:
        return text.format_map(_SafeFormat(payload or {}))
    except (ValueError, IndexError):
        return text


class AccentPulse(QWidget):
    """Тонкая цветная полоса поверх окна: вспышка → затухание → скрытие.

    Самоудаляется — никакого «перекрасили и забыли».
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        from PySide6.QtCore import QPropertyAnimation
        from PySide6.QtGui import QPalette
        self._palette_role = QPalette.ColorRole.Window
        self.setFixedHeight(5)
        self.setAutoFillBackground(True)
        self.hide()
        self._eff = QGraphicsOpacityEffect(self)
        self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.finished.connect(self._on_anim_finished)

    def pulse(self, color: str, duration_ms: int = 800) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        from PySide6.QtGui import QPalette
        self.setGeometry(0, 0, parent.width(), 5)
        pal = self.palette()
        pal.setColor(self._palette_role, QColor(color))
        self.setPalette(pal)
        self._anim.stop()
        self._eff.setOpacity(0.85)
        self.show()
        self.raise_()
        self._anim.setStartValue(0.85)
        self._anim.setEndValue(0.0)
        self._anim.setDuration(max(100, int(duration_ms)))
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._anim.endValue() == 0.0:
            self.hide()


class ExperienceManager(QObject):
    """Подписывается на события → исполняет действия пресета."""

    def __init__(self, toast_cb=None, pulse_cb=None, status_cb=None,
                 parent: QObject | None = None):
        super().__init__(parent)
        self._toast_cb = toast_cb
        self._pulse_cb = pulse_cb
        self._status_cb = status_cb
        self._mapping: dict[str, dict] = {}
        self._sounds_enabled = True
        self._player = None

    # ── конфигурация ──

    def configure(self, mapping: dict) -> None:
        self._mapping = {e: dict(a) for e, a in (mapping or {}).items()}

    def mapping(self) -> dict:
        return {e: dict(a) for e, a in self._mapping.items()}

    def set_sounds_enabled(self, enabled: bool) -> None:
        self._sounds_enabled = bool(enabled)

    def sounds_enabled(self) -> bool:
        return self._sounds_enabled

    # ── главная точка входа ──

    def handle(self, event: str, payload: dict | None = None) -> bool:
        """Обработать событие. False — событие неизвестно/без действий."""
        actions = self._mapping.get(event)
        if not actions:
            return False

        toast = actions.get("toast")
        if toast and self._toast_cb:
            self._toast_cb(resolve_text(toast["text"], payload),
                           toast.get("variant", "info"))

        sound = actions.get("sound")
        if sound and self._sounds_enabled:
            self._play(sound)

        pulse = actions.get("accent_pulse")
        if pulse and self._pulse_cb:
            self._pulse_cb(pulse["color"], pulse.get("duration_ms", 800))
        return True

    # ── звук ──

    def _play(self, tone_name: str) -> None:
        if QSoundEffect is None:
            return
        try:
            path = sounds.tone_path(tone_name)
        except Exception as e:
            if self._status_cb:
                self._status_cb(f"tone synth failed: {e}")
            return
        try:
            if self._player is None:
                self._player = QSoundEffect(self)
                self._player.setVolume(0.55)
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()
        except Exception as e:  # нет аудио-устройства — тихо и честно
            if self._status_cb:
                self._status_cb(f"audio playback unavailable: {e}")
