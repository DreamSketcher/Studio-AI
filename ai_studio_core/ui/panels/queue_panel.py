"""Queue — нижний dock (с таблицей задач)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ai_studio_core.i18n import t as tr

from ..controllers.queue_controller import QueueTask
from ..theme.tokens import TOKENS


class QueuePanel(QWidget):
    cancel_task = Signal(str)
    clear_completed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._table = QTableWidget(0, 5)
        self._apply_headers()
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            f"QTableWidget {{ "
            f"background: {TOKENS.colors.bg_primary}; "
            f"alternate-background-color: {TOKENS.colors.bg_secondary}; "
            f"gridline-color: {TOKENS.colors.border_default}; border: none; }}"
            f"QHeaderView::section {{ "
            f"background: {TOKENS.colors.bg_secondary}; color: {TOKENS.colors.text_secondary}; "
            f"border: none; border-bottom: 1px solid {TOKENS.colors.border_default}; "
            f"padding: 6px; font-weight: 600; font-size: {TOKENS.font_size.caption}px; }}"
        )
        layout.addWidget(self._table)

        bar = QHBoxLayout()
        bar.setContentsMargins(TOKENS.spacing.sm, TOKENS.spacing.xs,
                               TOKENS.spacing.sm, TOKENS.spacing.xs)
        bar.addStretch()
        self._btn_clear = QPushButton(tr("queue_clear_done"))
        self._btn_clear.clicked.connect(self.clear_completed.emit)
        bar.addWidget(self._btn_clear)
        layout.addLayout(bar)

    def _apply_headers(self) -> None:
        self._table.setHorizontalHeaderLabels([
            tr("queue_status"), tr("queue_type"), tr("queue_model"),
            tr("queue_progress"), tr("queue_actions"),
        ])

    def retranslate_ui(self) -> None:
        self._apply_headers()
        self._btn_clear.setText(tr("queue_clear_done"))

    def set_tasks(self, tasks: list[QueueTask]) -> None:
        self._table.setRowCount(0)
        for t in tasks:
            self._add_row(t)

    def _add_row(self, t: QueueTask) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        status_icon = {"running": "⏳", "queued": "⏸", "done": "✅",
                       "error": "❌", "cancelled": "⊘"}.get(t.status, "•")
        self._table.setItem(row, 0, QTableWidgetItem(f"{status_icon} {t.status}"))
        self._table.setItem(row, 1, QTableWidgetItem(t.type))
        self._table.setItem(row, 2, QTableWidgetItem(t.model))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(t.progress)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        self._table.setCellWidget(row, 3, bar)
        btn = QPushButton("✕")
        btn.setFixedWidth(32)
        btn.clicked.connect(lambda _=False, tid=t.id: self.cancel_task.emit(tid))
        self._table.setCellWidget(row, 4, btn)
