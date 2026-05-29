from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QIcon, QAction
from PyQt6.QtWidgets import QTableView, QMenu

from urh.models.PLabelTableModel import PLabelTableModel


class ProtocolLabelTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.delete_action = QAction("Delete selected labels", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_action.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.delete_action.triggered.connect(self.delete_selected_rows)
        self.addAction(self.delete_action)

    @property
    def selected_rows(self) -> list:
        return [i.row() for i in self.selectedIndexes()]

    def model(self) -> PLabelTableModel:
        return super().model()

    def create_context_menu(self):
        menu = QMenu(self)
        if self.model().rowCount() == 0:
            return menu

        menu.addAction(self.delete_action)
        return menu

    def contextMenuEvent(self, event):
        self.create_context_menu().exec(self.mapToGlobal(event.pos()))

    def delete_selected_rows(self):
        for row in sorted(self.selected_rows, reverse=True):
            self.model().remove_label_at(row)
