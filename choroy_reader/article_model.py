"""Stable article model: progress updates must not rebuild the card delegates."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class ArticleModel(QAbstractListModel):
    ArticleRole = Qt.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []

    def roleNames(self):
        return {self.ArticleRole: b'modelData'}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == self.ArticleRole and 0 <= index.row() < len(self.items):
            return self.items[index.row()]
        return None

    def update(self, items):
        if [x['link'] for x in items] != [x['link'] for x in self.items]:
            self.beginResetModel()
            self.items = items
            self.endResetModel()
            return
        for row, item in enumerate(items):
            if item != self.items[row]:
                self.items[row] = item
                self.dataChanged.emit(self.index(row), self.index(row), [self.ArticleRole])
