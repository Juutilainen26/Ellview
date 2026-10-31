"""v0.2.2: F2 파일 열기, B 책갈피 추가, F3 책갈피 목록, 넘김 영역 세로 가운데 30%."""
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeySequence, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.history import History
from ellview.ui.shortcuts import ACTIONS


@pytest.fixture()
def win(qapp):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.resize(1000, 700)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    w.viewer.setFocus()
    yield w
    w.close()


# ------------------------------------------------------------------ 단축키
def test_default_shortcuts_unique():
    seen = {}
    for aid, _label, keys, _cat in ACTIONS:
        for k in keys:
            t = QKeySequence(k).toString()
            assert t not in seen, f"{t}: {seen.get(t)} / {aid}"
            seen[t] = aid


def test_f2_and_ctrl_o_open_file(win, lib, monkeypatch):
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return lib["zip"], ""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(fake))
    QTest.keyClick(win, Qt.Key_F2)
    assert len(calls) == 1 and win.book is not None and win.book.path.endswith("02_한글.zip")
    QTest.keyClick(win, Qt.Key_O, Qt.ControlModifier)
    assert len(calls) == 2


def test_b_adds_bookmark_ctrl_d_does_nothing(win, lib, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("테스트", True)))
    win.open_any(lib["cbz"])
    QTest.keyClick(win, Qt.Key_D, Qt.ControlModifier)
    assert win.bookmarks.items == []
    QTest.keyClick(win, Qt.Key_B)
    assert len(win.bookmarks.items) == 1 and win.bookmarks.items[0].title == "테스트"


def test_f3_opens_bookmark_list_ctrl_b_does_nothing(win, lib, monkeypatch):
    from ellview.ui import dialogs
    opened = []
    monkeypatch.setattr(dialogs.BookmarksDialog, "exec", lambda self: opened.append(1) or 0)
    QTest.keyClick(win, Qt.Key_B, Qt.ControlModifier)
    assert opened == []
    QTest.keyClick(win, Qt.Key_F3)
    assert opened == [1]


def test_help_lists_new_keys(win):
    from ellview.ui.dialogs import shortcut_help_html
    html = shortcut_help_html({})
    assert "Ctrl+O, F2" in html and ">B<" in html and ">F3<" in html
    assert "Ctrl+D" not in html and "Ctrl+B" not in html


# ------------------------------------------------------------------ 넘김 영역
def test_zone_requires_vertical_middle(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer
    w, h = v.width(), v.height()
    for y_ratio, expect in ((0.05, None), (0.33, None), (0.36, "right"), (0.5, "right"),
                            (0.64, "right"), (0.67, None), (0.95, None)):
        assert v.zone_at(w - 5, h * y_ratio) == expect, y_ratio
    assert v.zone_at(5, h * 0.5) == "left" and v.zone_at(5, h * 0.1) is None


def test_corner_click_does_not_turn(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer
    for pt in (QPoint(v.width() - 5, 10), QPoint(v.width() - 5, v.height() - 10),
               QPoint(5, 10), QPoint(5, v.height() - 10)):
        QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, pt)
    assert win.index == 0
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(v.width() - 5, v.height() // 2))
    assert win.index == 1


def test_corner_double_click_is_fullscreen(win, lib, qapp):
    win.open_any(lib["folder"])
    v = win.viewer
    pt = QPoint(v.width() - 5, 15)
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, pt)
    QTest.mouseDClick(v, Qt.LeftButton, Qt.NoModifier, pt)
    qapp.processEvents()
    assert win.index == 0 and win.isFullScreen()
    win.act_escape()


def test_hover_only_in_band(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer

    def hover(x, y):
        QApplication.sendEvent(v, QMouseEvent(QEvent.MouseMove, QPointF(x, y), v.mapToGlobal(QPointF(x, y)),
                                              Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    hover(v.width() - 5, 10)
    assert v._hover_zone is None and v.cursor().shape() != Qt.PointingHandCursor
    hover(v.width() - 5, v.height() / 2)
    assert v._hover_zone == "right" and v.cursor().shape() == Qt.PointingHandCursor
    hover(v.width() - 5, v.height() - 5)
    assert v._hover_zone is None
