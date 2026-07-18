"""Главное окно — Workspace-контейнер с dock-панелями.

Layout:
┌──────────────────────────────────────────────────┐
│  Menu Bar                                        │
├──────────────────────────────────────────────────┤
│  [TTS]  [Chat]  [Image]  [Pipeline]    (tabs)   │
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
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget, QMainWindow, QMenuBar, QTabWidget, QWidget,
)

from .controllers import (
    ChatController, ModelController, QueueController, TTSController,
)
from .dialogs import AboutDialog, EnvSetupWizard, ModelDownloadDialog
from .panels import (
    HistoryPanel, ModelHubPanel, QueuePanel, SettingsPanel,
)
from .widgets.log_console import LogConsole
from .widgets.status_bar import ResourceStatusBar
from .widgets.toast import Toast
from .workspaces import ChatWorkspace, PipelineWorkspace, TTSWorkspace


class MainWindow(QMainWindow):
    _WINDOW_GEOMETRY_KEY = "mainwindow/geometry"
    _WINDOW_STATE_KEY = "mainwindow/state"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI Studio")
        self.setMinimumSize(1200, 750)
        self.resize(1280, 820)

        self._settings = QSettings("ai_studio", "studio")

        # Контроллеры
        self._tts_ctrl = TTSController()
        self._chat_ctrl = ChatController()
        self._model_ctrl = ModelController()
        self._queue_ctrl = QueueController()

        self._setup_menu_bar()
        self._setup_workspaces()
        self._setup_dock_panels()
        self._setup_status_bar()
        self._wire_controllers()
        self._restore_layout()

        # Стартовый toast
        QTimer = None
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._toast("Добро пожаловать в AI Studio", "info"))

    # ── Menu ──
    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self._make_action("New Project", "Ctrl+N", self._noop))
        file_menu.addAction(self._make_action("Open Project…", "Ctrl+O", self._noop))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Export…", "Ctrl+Shift+E", self._noop))
        file_menu.addSeparator()
        file_menu.addAction(self._make_action("Exit", "Ctrl+Q", self.close))

        self._view_menu = menu_bar.addMenu("&View")

        models_menu = menu_bar.addMenu("&Models")
        models_menu.addAction(self._make_action("Download Model…", "", self._on_download_model))
        models_menu.addAction(self._make_action("Manage Models…", "", self._noop))

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self._make_action("Environment Setup Wizard…", "", self._on_env_wizard))

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self._make_action("About", "", self._on_about))

    def _make_action(self, text: str, shortcut: str, slot) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        return a

    # ── Workspaces ──
    def _setup_workspaces(self) -> None:
        self._workspace_tabs = QTabWidget()
        self._workspace_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._workspace_tabs.setMovable(False)
        self._workspace_tabs.setDocumentMode(True)

        self._tts_workspace = TTSWorkspace(controller=self._tts_ctrl)
        self._chat_workspace = ChatWorkspace(controller=self._chat_ctrl)
        self._pipeline_workspace = PipelineWorkspace()

        self._workspace_tabs.addTab(self._tts_workspace, "🎙  TTS")
        self._workspace_tabs.addTab(self._chat_workspace, "💬  Chat")
        self._workspace_tabs.addTab(self._pipeline_workspace, "🔗  Pipeline")

        self.setCentralWidget(self._workspace_tabs)

    # ── Dock panels ──
    def _setup_dock_panels(self) -> None:
        self._model_hub = self._create_dock(
            "Model Hub", ModelHubPanel(), Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._settings_dock = self._create_dock(
            "Settings", SettingsPanel(), Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._queue_dock = self._create_dock(
            "Queue", QueuePanel(), Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self._log_dock = self._create_dock(
            "Console", LogConsole(), Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.tabifyDockWidget(self._queue_dock, self._log_dock)

        self._history_dock = self._create_dock(
            "History", HistoryPanel(), Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.tabifyDockWidget(self._model_hub, self._history_dock)
        self._model_hub.raise_()

        # Подключаем сигналы панелей
        self._queue_widget = self._queue_dock.widget()
        self._history_widget = self._history_dock.widget()
        self._model_widget = self._model_hub.widget()
        self._log_widget = self._log_dock.widget()

    def _create_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.addDockWidget(area, dock)
        if hasattr(self, "_view_menu") and self._view_menu is not None:
            self._view_menu.addAction(dock.toggleViewAction())
        return dock

    # ── Status bar ──
    def _setup_status_bar(self) -> None:
        self._resource_bar = ResourceStatusBar()
        self.setStatusBar(self._resource_bar)
        self._resource_bar.set_message("Ready")

    # ── Wiring controllers <→ UI ──
    def _wire_controllers(self) -> None:
        # TTS
        self._tts_workspace.generate_requested.connect(self._tts_ctrl.on_generate)
        self._tts_workspace.stop_requested.connect(self._tts_ctrl.on_stop)
        self._tts_ctrl.busy_changed.connect(self._tts_workspace.set_busy)
        self._tts_ctrl.status_message.connect(self._resource_bar.set_message)
        self._tts_ctrl.generation_progress.connect(
            lambda pct, _s: self._tts_workspace.pipeline().set_step_state(3, "active") if self._tts_workspace.pipeline() else None
        )
        self._tts_ctrl.pipeline_step_changed.connect(
            lambda idx, state: self._tts_workspace.pipeline().set_step_state(idx, state) if self._tts_workspace.pipeline() else None
        )
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

        # Model hub
        self._model_widget.download_requested.connect(self._model_ctrl.download_model)
        self._model_ctrl.status_message.connect(self._resource_bar.set_message)
        self._model_ctrl.log_message.connect(self._log_widget.append)

        # Queue
        self._queue_widget.cancel_task.connect(self._queue_ctrl.cancel_task)
        self._queue_widget.clear_completed.connect(self._queue_ctrl.clear_completed)
        self._queue_ctrl.queue_changed.connect(self._queue_widget.set_tasks)
        self._queue_widget.set_tasks(self._queue_ctrl.tasks())

    def _on_tts_done(self, output_path: str) -> None:
        self._resource_bar.set_message(f"Generated: {output_path}")
        self._toast(f"Generation complete\n{output_path}", "success")

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

    # ── Menu slots ──
    def _noop(self) -> None:
        self._toast("Этот пункт меню — заглушка в демо UI", "info")

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
        t = Toast(message, variant=variant, duration_ms=3000, parent=self)
        t.show_at(self)
