"""Settings — правый dock. Реальные настройки: язык, тема, устройство, пути.

Раньше здесь была заглушка `settings_changed = None`, из-за которой любой
вызов emit() падал с AttributeError при переключении языка.
Теперь сигналы настоящие, а списки отражают только реально доступные опции.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import LANGUAGES, t as tr

from ..diag_bridge import get_bridge
from ..theme.tokens import TOKENS
from ..widgets.collapsible_group import CollapsibleGroup


def _cuda_available() -> bool:
    """CUDA есть только если диагностика подтвердила рабочий torch и видимый GPU.

    Прямой import torch в GUI‑процессе на старте окна не делаем — битый
    torch может убить процесс до window.show(). После завершения фоновой
    диагностики bridge обновит статус и панель перестроит комбобокс.
    """
    try:
        return get_bridge().cuda_available()
    except Exception:
        return False


class SettingsPanel(QWidget):
    settings_changed = Signal(dict)     # полный снапшот настроек
    language_changed = Signal(str)      # код языка ("en"/"ru")
    paths_changed = Signal(str, str)    # (kind: "models"/"output", path)
    llm_saved = Signal(str)             # id сохранённого провайдера

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._dirs = {"models": "models/", "output": "outputs/"}

        layout = QVBoxLayout(self)
        layout.setSpacing(TOKENS.spacing.sm)
        layout.setContentsMargins(
            TOKENS.spacing.sm, TOKENS.spacing.sm,
            TOKENS.spacing.sm, TOKENS.spacing.sm,
        )

        # ── General ──
        self._gen_group = CollapsibleGroup("")
        gen_form = QFormLayout()
        self._theme = QComboBox()
        self._theme.addItem(tr("theme_dark"), userData="dark")
        # Light/System не добавляем: в теме только тёмная палитра —
        # выбирать несуществующее нельзя.
        self._theme_lbl = QLabel()
        gen_form.addRow(self._theme_lbl, self._theme)

        self._lang = QComboBox()
        for code, name in LANGUAGES.items():
            self._lang.addItem(name, userData=code)
        self._lang_lbl = QLabel()
        gen_form.addRow(self._lang_lbl, self._lang)

        self._auto_save = QCheckBox()
        self._auto_save.setChecked(True)
        gen_form.addRow(self._auto_save)
        self._gen_group.set_content_layout(gen_form)
        layout.addWidget(self._gen_group)

        # ── Performance ──
        self._perf_group = CollapsibleGroup("")
        perf_form = QFormLayout()
        self._device = QComboBox()
        self._device_lbl = QLabel()
        perf_form.addRow(self._device_lbl, self._device)
        self._rebuild_device_combo()

        self._threads = QSpinBox()
        self._threads.setRange(1, 32)
        self._threads.setValue(4)
        self._threads_lbl = QLabel()
        perf_form.addRow(self._threads_lbl, self._threads)

        self._batch = QSpinBox()
        self._batch.setRange(1, 64)
        self._batch.setValue(1)
        self._batch_lbl = QLabel()
        perf_form.addRow(self._batch_lbl, self._batch)
        self._perf_group.set_content_layout(perf_form)
        layout.addWidget(self._perf_group)

        # ── Paths ──
        self._paths_group = CollapsibleGroup("")
        paths_form = QFormLayout()
        self._models_path = QPushButton("📁 models/")
        self._models_path.clicked.connect(lambda: self._choose_dir("models"))
        self._models_lbl = QLabel()
        paths_form.addRow(self._models_lbl, self._models_path)

        self._output_path = QPushButton("📁 outputs/")
        self._output_path.clicked.connect(lambda: self._choose_dir("output"))
        self._output_lbl = QLabel()
        paths_form.addRow(self._output_lbl, self._output_path)
        self._paths_group.set_content_layout(paths_form)
        layout.addWidget(self._paths_group)

        # ── LLM Provider (реальные ключи/провайдер через gpt_client) ──
        self._llm_group = CollapsibleGroup("")
        llm_form = QFormLayout()

        from PySide6.QtWidgets import QLineEdit
        self._provider = QComboBox()
        self._provider_lbl = QLabel()
        llm_form.addRow(self._provider_lbl, self._provider)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setClearButtonEnabled(True)
        self._api_key_lbl = QLabel()
        llm_form.addRow(self._api_key_lbl, self._api_key)

        self._key_state = QLabel()
        self._key_state.setStyleSheet(
            f"color: {TOKENS.colors.text_secondary}; "
            f"font-size: {TOKENS.font_size.caption}px;"
        )
        llm_form.addRow(self._key_state)

        self._btn_save_llm = QPushButton()
        self._btn_save_llm.clicked.connect(self._save_llm)
        llm_form.addRow(self._btn_save_llm)

        # Все виджеты группы созданы — можно безопасно наполнять комбобокс
        self._provider.currentIndexChanged.connect(lambda _i: self._refresh_key_state())
        self._rebuild_providers()

        self._llm_group.set_content_layout(llm_form)
        layout.addWidget(self._llm_group)

        # ── About ──
        self._about_group = CollapsibleGroup("")
        about_form = QVBoxLayout()
        about_form.addWidget(QLabel(
            "AI Studio v0.1.0\nExtracted from XTTS-Studio-AI\nHeadless core + PySide6 UI"
        ))
        self._about_group.set_content_layout(about_form)
        layout.addWidget(self._about_group)

        layout.addStretch()

        # ── Wiring ──
        self._lang.currentIndexChanged.connect(self._on_lang_index)
        self._theme.currentIndexChanged.connect(lambda _i: self._emit_settings())
        self._device.currentIndexChanged.connect(lambda _i: self._emit_settings())
        self._threads.valueChanged.connect(lambda _v: self._emit_settings())
        self._batch.valueChanged.connect(lambda _v: self._emit_settings())
        self._auto_save.toggled.connect(lambda _v: self._emit_settings())

        self.retranslate_ui()

    def _rebuild_device_combo(self) -> None:
        """Перестроить комбобокс устройства после получения диагностики CUDA."""
        current = self._device.currentData() if self._device.count() else "auto"
        self._device.blockSignals(True)
        self._device.clear()
        self._device.addItem(tr("device_auto"), userData="auto")
        self._device.addItem("CPU", userData="cpu")
        if _cuda_available():
            name = get_bridge().cuda_device_name() or "CUDA"
            self._device.addItem(f"CUDA — {name}", userData="cuda")
        # Вернуть предыдущий выбор (если его нет — auto)
        idx = self._device.findData(current)
        if idx >= 0:
            self._device.setCurrentIndex(idx)
        self._device.blockSignals(False)

    def refresh_device_options(self) -> None:
        """Публичный слот для подписки на diagnostics_updated / cuda_info_changed."""
        self._rebuild_device_combo()

    # ── Public API ──

    def current_settings(self) -> dict:
        return {
            "language": self.language(),
            "theme": self._theme.currentData(),
            "device": self._device.currentData(),
            "worker_threads": self._threads.value(),
            "batch_size": self._batch.value(),
            "auto_save": self._auto_save.isChecked(),
            "models_dir": self._dirs["models"],
            "output_dir": self._dirs["output"],
        }

    def language(self) -> str:
        return self._lang.currentData() or "en"

    def set_language(self, code: str) -> None:
        """Программно выставляет язык в комбобоксе (без эмиссии сигналов)."""
        idx = self._lang.findData(code)
        if idx >= 0:
            self._lang.blockSignals(True)
            self._lang.setCurrentIndex(idx)
            self._lang.blockSignals(False)

    def set_dir(self, kind: str, path: str) -> None:
        if kind in self._dirs and path:
            self._dirs[kind] = path
            btn = self._models_path if kind == "models" else self._output_path
            btn.setText(f"📁 {path}")

    def retranslate_ui(self) -> None:
        self._gen_group.set_title(tr("set_general"))
        self._theme_lbl.setText(tr("set_theme"))
        self._theme.setItemText(0, tr("theme_dark"))
        self._lang_lbl.setText(tr("set_language"))
        self._auto_save.setText(tr("set_autosave"))
        self._perf_group.set_title(tr("set_performance"))
        self._device_lbl.setText(tr("set_device"))
        self._device.setItemText(0, tr("device_auto"))
        self._threads_lbl.setText(tr("set_threads"))
        self._batch_lbl.setText(tr("set_batch"))
        self._paths_group.set_title(tr("set_paths"))
        self._models_lbl.setText(tr("set_models_dir"))
        self._output_lbl.setText(tr("set_output_dir"))
        self._llm_group.set_title(tr("set_llm"))
        self._provider_lbl.setText(tr("set_provider"))
        self._api_key_lbl.setText(tr("set_api_key"))
        self._api_key.setPlaceholderText(tr("set_api_key_ph"))
        self._btn_save_llm.setText(tr("set_save"))
        # Подписи провайдеров зависят от языка — перечитываем из gpt_client
        self._rebuild_providers()
        self._about_group.set_title(tr("set_about"))

    # ── LLM provider (real gpt_client persistence) ──

    def _rebuild_providers(self) -> None:
        """Наполняет комбобокс провайдеров из gpt_client (с подписями i18n)."""
        try:
            from ai_studio_core import gpt_client
            gpt_client.refresh_i18n_labels()
            providers = []
            for pid, info in gpt_client.PROVIDERS.items():
                providers.append((pid, info.get("label", pid)))
            for entry in gpt_client.list_custom_providers():
                if entry.get("id") not in gpt_client.PROVIDERS:
                    providers.append((entry["id"], entry.get("label", entry["id"])))
            current = gpt_client.get_provider()
        except Exception:
            providers, current = [], ""
        self._provider.blockSignals(True)
        self._provider.clear()
        for pid, label in providers:
            self._provider.addItem(label, userData=pid)
        if current:
            idx = self._provider.findData(current)
            if idx >= 0:
                self._provider.setCurrentIndex(idx)
        self._provider.blockSignals(False)
        self._refresh_key_state()

    def selected_provider(self) -> str:
        return self._provider.currentData() or ""

    def _refresh_key_state(self) -> None:
        pid = self.selected_provider()
        configured = False
        if pid:
            try:
                from ai_studio_core import gpt_client
                configured = bool(gpt_client.get_api_key(pid)) or pid == "local"
            except Exception:
                configured = False
        key = "set_key_state_ok" if configured else "set_key_state_missing"
        self._key_state.setText(tr(key))
        color = TOKENS.colors.accent_success if configured else TOKENS.colors.accent_warning
        self._key_state.setStyleSheet(
            f"color: {color}; font-size: {TOKENS.font_size.caption}px;"
        )

    def _save_llm(self) -> None:
        pid = self.selected_provider()
        if not pid:
            return
        try:
            from ai_studio_core import gpt_client
            gpt_client.set_provider(pid)
            key = self._api_key.text().strip()
            if key:
                gpt_client.set_api_key(key, pid)
                self._api_key.clear()
        except Exception as e:
            self._key_state.setText(f"⚠ {type(e).__name__}: {e}")
            return
        self._refresh_key_state()
        self.llm_saved.emit(pid)

    # ── Internals ──

    def _on_lang_index(self, _index: int) -> None:
        self.language_changed.emit(self.language())
        self._emit_settings()

    def _emit_settings(self) -> None:
        self.settings_changed.emit(self.current_settings())

    def _choose_dir(self, kind: str) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("set_choose_dir"))
        if path:
            self.set_dir(kind, path)
            self.paths_changed.emit(kind, path)
            self._emit_settings()
