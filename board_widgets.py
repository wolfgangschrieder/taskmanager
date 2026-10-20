"""Drag-and-drop task lists with stable database identifiers."""
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QListWidget, QAbstractItemView


MIME = "application/x-apex-task-id"


class TaskList(QListWidget):
    moved = Signal(int, int, int)  # task_id, lane_id, destination index

    def __init__(self, lane_id, parent=None):
        super().__init__(parent)
        self.lane_id = lane_id
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(5)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(MIME, str(item.data(Qt.ItemDataRole.UserRole)).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(MIME):
            event.ignore()
            return
        try:
            task_id = int(bytes(event.mimeData().data(MIME)).decode())
        except ValueError:
            event.ignore()
            return
        target = self.itemAt(event.position().toPoint())
        index = self.row(target) if target else self.count()
        self.moved.emit(task_id, self.lane_id, index)
        event.acceptProposedAction()
