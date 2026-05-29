from PyQt6.QtWidgets import QTreeView
from PyQt6.QtCore import pyqtSignal, QItemSelectionModel


class ModulatorTreeView(QTreeView):
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def model(self):
        return super().model()

    def selectionModel(self) -> QItemSelectionModel:
        return super().selectionModel()

    def selectionChanged(self, QItemSelection, QItemSelection_1):
        self.selection_changed.emit()
        super().selectionChanged(QItemSelection, QItemSelection_1)
