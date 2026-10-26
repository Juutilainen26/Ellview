"""썸네일 목록 패널: 화면에 보이는 항목만 백그라운드에서 작게 디코딩합니다."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem

from ellview.core.loader import decode

THUMB = QSize(120, 168)


class _Sig(QObject):
    done = Signal(str, int, object)


class _ThumbTask(QRunnable):
    def __init__(self, book, index, sig):
        super().__init__()
        self.book, self.index, self.sig = book, index, sig

    def run(self):
        try:
            data = self.book.read(self.index)
            d = decode(data, self.book.pages[self.index].name, target=THUMB, detect_animation=False)
            img = d.image
        except Exception:
            img = None
        try:
            self.sig.done.emit(self.book.path, self.index, img)
        except RuntimeError:
            pass


class ThumbnailList(QListWidget):
    pageClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.TopToBottom)
        self.setWrapping(False)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setIconSize(THUMB)
        self.setGridSize(QSize(THUMB.width() + 16, THUMB.height() + 30))
        self.setSpacing(2)
        self.setMinimumWidth(THUMB.width() + 40)
        self.setTextElideMode(Qt.ElideMiddle)
        self.book = None
        self._requested: set[int] = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self._sig = _Sig()
        self._sig.done.connect(self._on_thumb)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._load_visible)
        self.verticalScrollBar().valueChanged.connect(lambda _: self._timer.start())
        self.itemClicked.connect(lambda it: self.pageClicked.emit(self.row(it)))
        ph = QPixmap(THUMB)
        ph.fill(QColor(60, 60, 64))
        self._placeholder = QIcon(ph)

    def set_book(self, book):
        self.pool.clear()
        self.clear()
        self._requested.clear()
        self.book = book
        if book is None:
            return
        for i, p in enumerate(book.pages):
            it = QListWidgetItem(self._placeholder, f"{i + 1}. {p.display_name}")
            it.setToolTip(p.name)
            it.setSizeHint(self.gridSize())
            self.addItem(it)
        self._timer.start()

    def set_current(self, index: int):
        if 0 <= index < self.count():
            self.blockSignals(True)
            self.setCurrentRow(index)
            self.blockSignals(False)
            self.scrollToItem(self.item(index), QListWidget.PositionAtCenter)
            self._timer.start()

    def showEvent(self, e):
        super().showEvent(e)
        self._timer.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def _load_visible(self):
        if self.book is None or not self.isVisible() or self.count() == 0:
            return
        top = self.indexAt(self.viewport().rect().topLeft() + QPoint(5, 5))
        first = top.row() if top.isValid() else 0
        per_view = max(1, self.viewport().height() // self.gridSize().height() + 2)
        for i in range(max(0, first - 2), min(self.count(), first + per_view + 3)):
            if i not in self._requested:
                self._requested.add(i)
                self.pool.start(_ThumbTask(self.book, i, self._sig))

    def _on_thumb(self, path, index, img):
        if self.book is None or path != self.book.path or index >= self.count():
            return
        if img is not None and not img.isNull():
            self.item(index).setIcon(QIcon(QPixmap.fromImage(img)))
