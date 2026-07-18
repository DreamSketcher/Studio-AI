"""Главное окно — Workspace-контейнер с dock-панелями.

Layout:
┌──────────────────────────────────────────────────┐
│  Menu Bar                                        │
├──────────────────────────────────────────────────┤
│  [TTS]  [Chat]  [Image]  [Pipeline]    (tabs)    │
├────────┬─────────────────────────┬───────────────┤
│        │                         │               │
│ Model  │   Active Workspace      │   Settings    │
│ Hub    │      (central)          │   / Inspector │
│/History│                         │               │
├────────┴─────────────────────────┴───────────────┤
│  Queue / Log Console          (bottom dock)      │
├──────────────────────────────────────────────────┤
│  Status: GPU% │ VRAM │ CPU% │ Queue size         │
└──────────────────────────────────────────────────┘

Язык интерфейса переключается на лету (Settings → Language → retranslate).
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget, QMainWindow, QTabWidget, QWidget,
)

from ai_studio_core import i18n
from ai_studio_core.i18n import t as tr

from .controllers import (
    ChatController, ModelController, QueueController, TTSController,
)
from .dialogs import AboutDialog, EnvSetupWizard, ModelDownloadDialog
from .panels import (
    HistoryPanel, InspectorPanel, ModelHubPanel, QueuePanel, SettingsPanel,
)
from .widgets.log_console import LogConsole
from .widgets.status_bar import ResourceStatusBar
from .widgets.toast import Toast
from .workspaces import (
    ChatWorkspace, ImageWorkspace, PipelineWorkspace, TTSWorkspace,
)


class MainWindow(QMainWindow):
    _WINDOW_GEOMETRY_KEY = "mainwindow/geometry"
    _WINDOW_STATE_KEY = "mainwindow/state"
    _LANGUAGE_KEY = "ui/language"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI Studio")
        self.setMinimumSize(1200, 750)
        self.resize(1280, 820)

        self._settings = QSettings("ai_studio", "studio")

        # Язык восстанавливаем ДО построения виджетов (app.py уже применил его,
        # но повторная установка idempotent и спасает при прямом создании окна)
        saved_lang = self._settings.value(self._LANGUAGE_KEY, None)
        if saved_lang:
            i18n.set_language(str(saved_lang))

        # Контроллеры
        self._tts_ctrl = TTSController()
        self._chat_ctrl = ChatController()
        self._model_ctrl = ModelController()
        self._queue_ctrl = QueueController()

        self._menu_map: list[tuple[object, str]] = []   # (QMenu, i18n key)
        self._action_map: list[tuple[QAction, str]] = []
        self._dock_map: list[tuple[QDockWidget, str]] = []
        self._tab_map: list[tuple[int, str]] = []

        self._setup_menu_bar()
        self._setup_workspaces()
        self._setup_dock_panels()
        self._setup_status_bar()
        self._wire_controllers()
        self._wire_settings()
        self._restore_layout()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._toast(tr("msg_welcome"), "info"))

    # ── Menu ──
    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("")
        self._menu_map.append((file_menu, "menu_file"))
        self._add_menu_action(file_menu, "act_new_project", "Ctrl+N", self._on_new_project)
        self._add_menu_action(file_menu, "act_open_project", "Ctrl+O", self._on_open_project)
        self._add_menu_action(file_menu, "act_save_project", "Ctrl+S", self._on_save_project)
        file_menu.addSeparator()
        self._add_menu_action(file_menu, "act_export", "Ctrl+Shift+E", self._on_export)
        file_menu.addSeparator()
        self._add_menu_action(file_menu, "act_exit", "Ctrl+Q", self.close)

        self._view_menu = menu_bar.addMenu("")
        self._menu_map.append((self._view_menu, "menu_view"))

        models_menu = menu_bar.addMenu("")
        self._menu_map.append((models_menu, "menu_models"))
        self._add_menu_action(models_menu, "act_download_model", "", self._on_download_model)
        self._add_menu_action(models_menu, "act_manage_models", "", self._on_manage_models)

        tools_menu = menu_bar.addMenu("")
        self._menu_map.append((tools_menu, "menu_tools"))
        self._add_menu_action(tools_menu, "act_env_wizard", "", self._on_env_wizard)

        help_menu = menu_bar.addMenu("")
        self._menu_map.append((help_menu, "menu_help"))
        self._add_menu_action(help_menu, "act_about", "", self._on_about)

        self.retranslate_menus()

    def _add_menu_action(self, menu, key: str, shortcut: str, slot) -> QAction:
        a = QAction("", self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        self._action_map.append((a, key))
        return a

    def retranslate_menus(self) -> None:
        for menu, key in self._menu_map:
            menu.setTitle(tr(key))
        for action, key in self._action_map:
            action.setText(tr(key))

    # ── Workspaces ──
    def _setup_workspaces(self) -> None:
        self._workspace_tabs = QTabWidget()
        self._workspace_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._workspace_tabs.setMovable(False)
        self._workspace_tabs.setDocumentMode(True)

        self._tts_workspace = TTSWorkspace(controller=self._tts_ctrl)
        self._chat_workspace = ChatWorkspace(controller=self._chat_ctrl)
        self._image_workspace = ImageWorkspace()
        self._pipeline_workspace = PipelineWorkspace()

        self._tab_map = []
        self._add_workspace_tab(self._tts_workspace, "tab_tts")
        self._add_workspace_tab(self._chat_workspace, "tab_chat")
        self._add_workspace_tab(self._image_workspace, "tab_image")
        self._add_workspace_tab(self._pipeline_workspace, "tab_pipeline")

        self.setCentralWidget(self._workspace_tabs)

    def _add_workspace_tab(self, widget: QWidget, key: str) -> None:
        idx = self._workspace_tabs.addTab(widget, tr(key))
        self._tab_map.append((idx, key))

    # ── Dock panels ──
    def _setup_dock_panels(self) -> None:
        self._model_hub = self._create_dock(
            "dock_model_hub", ModelHubPanel(), Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._settings_dock = self._create_dock(
            "dock_settings", SettingsPanel(), Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._inspector_dock = self._create_dock(
            "dock_inspector", InspectorPanel(), Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.tabifyDockWidget(self._settings_dock, self._inspector_dock)
        self._settings_dock.raise_()

        self._queue_dock = self._create_dock(
            "dock_queue", QueuePanel(), Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self._log_dock = self._create_dock(
            "dock_console", LogConsole(), Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.tabifyDockWidget(self._queue_dock, self._log_dock)

        self._history_dock = self._create_dock(
            "dock_history", HistoryPanel(), Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.tabifyDockWidget(self._model_hub, self._history_dock)
        self._model_hub.raise_()

        # Подключаем сигналы панелей
        self._queue_widget = self._queue_dock.widget()
        self._history_widget = self._history_dock.widget()
        self._model_widget = self._model_hub.widget()
        self._settings_widget = self._settings_dock.widget()
        self._inspector_widget = self._inspector_dock.widget()
        self._log_widget = self._log_dock.widget()

    def _create_dock(self, title_key: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(tr(title_key), self)
        dock.setObjectName(f"dock_{title_key}")  # обязателен для saveState()
        dock.setWidget(widget)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.addDockWidget(area, dock)
        self._dock_map.append((dock, title_key))
        if hasattr(self, "_view_menu") and self._view_menu is not None:
            self._view_menu.addAction(dock.toggleViewAction())
        return dock

    # ── Status bar ──
    def _setup_status_bar(self) -> None:
        self._resource_bar = ResourceStatusBar()
        self.setStatusBar(self._resource_bar)
        self._resource_bar.set_message(tr("msg_ready"))

    # ── Settings → language/theme/paths ──
    def _wire_settings(self) -> None:
        sp = self._settings_widget
        # Комбоксокс показывает текущий язык (без эмиссии)
        sp.set_language(i18n.get_language())
        sp.language_changed.connect(self._on_language_changed)
        sp.settings_changed.connect(self._on_settings_changed)
        sp.paths_changed.connect(self._on_paths_changed)

    def _on_language_changed(self, code: str) -> None:
        if not i18n.set_language(code):
            return
        self._settings.setValue(self._LANGUAGE_KEY, code)
        self.retranslate_ui()
        # Подписи провайдеров в gpt_client тоже зависят от языка
        try:
            from ai_studio_core import gpt_client
            gpt_client.refresh_i18n_labels()
        except Exception:
            pass
        self._log_widget.append("INFO", f"Language switched: {code}")

    def _on_settings_changed(self, settings: dict) -> None:
        self._app_settings = settings

    def _on_paths_changed(self, kind: str, path: str) -> None:
        self._log_widget.append("INFO", f"Path changed: {kind} -> {path}")

    def retranslate_ui(self) -> None:
        """Живое переключение языка без пересоздания виджетов."""
        self.retranslate_menus()
        for idx, key in self._tab_map:
            self._workspace_tabs.setTabText(idx, tr(key))
        for dock, key in self._dock_map:
            dock.setWindowTitle(tr(key))
        for ws in (self._tts_workspace, self._chat_workspace,
                   self._image_workspace, self._pipeline_workspace):
            ws.retranslate_ui()
        for panel in (self._settings_widget, self._inspector_widget,
                      self._model_widget, self._history_widget, self._queue_widget):
            panel.retranslate_ui()

    # ── Wiring controllers <→ UI ──
    def _wire_controllers(self) -> None:
        # TTS (очередь задач получает реальные задачи генерации)
        self._tts_ctrl.attach_queue(self._queue_ctrl)
        self._tts_workspace.generate_requested.connect(self._tts_ctrl.on_generate)
        self._tts_workspace.stop_requested.connect(self._tts_ctrl.on_stop)
        self._tts_workspace.export_requested.connect(self._on_export)
        self._tts_ctrl.busy_changed.connect(self._tts_workspace.set_busy)
        self._tts_ctrl.status_message.connect(self._resource_bar.set_message)
        self._tts_ctrl.pipeline_step_changed.connect(self._on_tts_step)
        self._tts_ctrl.generation_complete.connect(self._on_tts_done)
        self._tts_ctrl.log_message.connect(self._log_widget.append)
        self._tts_ctrl.error_occurred.connect(lambda msg: self._toast(msg, "error"))

        # Chat
        self._chat_workspace.send_requested.connect(self._chat_ctrl.on_send)
        self._chat_workspace.stop_requested.connect(self._chat_ctrl.on_stop)
        self._chat_workspace.clear_requested.connect(self._chat_ctrl.on_clear)
        self._chat_ctrl.message_added.connect(self._chat_workspace.add_message)
        self._chat_ctrl.busy_changed.connect(self._chat_workspace.set_busy)
        self._chat_ctrl.status_message.connect(self._resource_bar.set_message)
        self._chat_ctrl.log_message.connect(self._log_widget.append)
        self._chat_ctrl.error_occurred.connect(lambda msg: self._toast(msg, "error"))

        # History: выбор элемента → Inspector
        self._history_widget.item_selected.connect(self._on_history_selected)

        # Model hub
        self._model_widget.download_requested.connect(self._model_ctrl.download_model)
        self._model_widget.delete_requested.connect(self._model_ctrl.delete_model)
        self._model_ctrl.status_message.connect(self._resource_bar.set_message)
        self._model_ctrl.log_message.connect(self._log_widget.append)

        # Queue
        self._queue_widget.cancel_task.connect(self._queue_ctrl.cancel_task)
        self._queue_widget.clear_completed.connect(self._queue_ctrl.clear_completed)
        self._queue_ctrl.queue_changed.connect(self._queue_widget.set_tasks)
        self._queue_widget.set_tasks(self._queue_ctrl.tasks())

    def _on_tts_step(self, idx: int, state: str) -> None:
        strip = self._tts_workspace.pipeline()
        if strip is not None:
            strip.set_step_state(idx, state)

    def _on_tts_done(self, output_path: str) -> None:
        self._resource_bar.set_message(f'{tr("msg_generation_complete")}: {output_path}')
        self._toast(f'{tr("msg_generation_complete")}\n{output_path}', "success")
        # Реальная волна + воспроизведение + экспорт
        try:
            wf = self._tts_workspace.waveform_widget()
            wf.set_audio(output_path)
            self._tts_workspace.set_export_available(True)
            if self._tts_workspace.autoplay_checked():
                wf._toggle_play()
        except Exception as e:
            self._log_widget.append("WARN", f"waveform load failed: {e}")
        # История обновляется с диска — записи реальные
        self._history_widget.refresh()

    def _on_history_selected(self, path: str) -> None:
        import os
        props = {}
        try:
            st = os.stat(path)
            props = {
                "Size": f"{st.st_size / (1024 * 1024):.2f} MB",
                "Path": path,
            }
        except OSError:
            props = {"Path": path}
        self._inspector_widget.show_item(
            os.path.basename(path), "TTS", props,
            details=path,
        )

    # ── Layout persistence ──
    def _restore_layout(self) -> None:
        geom = self._settings.value(self._WINDOW_GEOMETRY_KEY)
        state = self._settings.value(self._WINDOW_STATE_KEY)
        if isinstance(geom, QByteArray):
            self.restoreGeometry(geom)
        if isinstance(state, QByteArray):
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        self._settings.setValue(self._WINDOW_GEOMETRY_KEY, self.saveGeometry())
        self._settings.setValue(self._WINDOW_STATE_KEY, self.saveState())
        super().closeEvent(event)

    # ── Menu slots (реальные реализации подключаются поэтапно) ──
    def _on_new_project(self) -> None:
        self._toast(tr("msg_menu_stub"), "info")

    def _on_open_project(self) -> None:
        self._toast(tr("msg_menu_stub"), "info")

    def _on_save_project(self) -> None:
        self._toast(tr("msg_menu_stub"), "info")

    def _on_export(self) -> None:
        """Реальный экспорт последнего сгенерированного аудио."""
        last = self._tts_ctrl.last_output()
        if not last:
            self._toast(tr("msg_nothing_to_export"), "warning")
            return
        import os
        from PySide6.QtWidgets import QFileDialog
        ext = os.path.splitext(last)[1].lower().lstrip(".") or "wav"
        suggested = os.path.basename(last)
        target, _sel = QFileDialog.getSaveFileName(
            self, tr("dlg_save_audio"), suggested,
            "Audio (*.wav *.mp3 *.flac *.ogg)",
        )
        if not target:
            return
        # Пользователь мог не дописать расширение — берём формат источника
        if not os.path.splitext(target)[1]:
            target = f"{target}.{ext}"
        try:
            out = self._tts_ctrl.export_last(target)
        except Exception as e:
            self._toast(f'{tr("ctl_export_fail")}\n{type(e).__name__}: {e}', "error")
            self._log_widget.append("ERROR", f"export failed: {e}")
            return
        self._toast(f'{tr("ctl_export_done")}\n{out}', "success")
        self._resource_bar.set_message(f'{tr("ctl_export_done")} {out}')

    def _on_manage_models(self) -> None:
        self._toast(tr("msg_menu_stub"), "info")

    def _on_download_model(self) -> None:
        dlg = ModelDownloadDialog(self)
        dlg.exec()

    def _on_env_wizard(self) -> None:
        wiz = EnvSetupWizard(self)
        wiz.exec()

    def _on_about(self) -> None:
        AboutDialog(self).exec()

    # ── Toast helper ──
    def _toast(self, message: str, variant: str = "info") -> None:
        t_ = Toast(message, variant=variant, duration_ms=3000, parent=self)
        t_.show_at(self)
