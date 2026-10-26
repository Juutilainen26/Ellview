"""GUI 동작 테스트 (오프스크린). 실제 창을 띄워 열기/이동/경계/두 페이지/책갈피를 확인."""
import os
import shutil
import time

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.history import History


@pytest.fixture()
def win(qapp, tmp_path):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.resize(1000, 760)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    w.viewer.setFocus()
    yield w
    w.close()
    qapp.processEvents()


def pump(qapp, ms=50):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)


def names(w):
    return [p.name for p in w.viewer.pages]


# ------------------------------------------------------------------ 1단계
def test_open_folder_and_navigate(win, lib, qapp):
    assert win.open_any(lib["folder"])
    assert names(win) == ["1.jpg"]
    win.act_next_page()
    assert names(win) == ["2.png"]
    win.act_last_page()
    assert names(win) == ["10.gif"]
    assert win.viewer.pages[0].player is not None, "GIF 재생기 생성"
    pump(qapp, 300)
    win.act_first_page()
    assert win.index == 0


def test_keyboard_shortcuts(win, lib, qapp):
    win.open_any(lib["folder"])
    win.viewer.setFocus()
    QTest.keyClick(win, Qt.Key_Right)
    assert win.index == 1
    QTest.keyClick(win, Qt.Key_Left)
    assert win.index == 0
    QTest.keyClick(win, Qt.Key_End)
    assert win.index == 5
    QTest.keyClick(win, Qt.Key_Home)
    assert win.index == 0


def test_wheel_navigation(win, lib, qapp):
    win.open_any(lib["folder"])
    v = win.viewer
    ev = QWheelEvent(QPointF(100, 100), QPointF(v.mapToGlobal(QPoint(100, 100))), QPoint(0, 0), QPoint(0, -120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    qapp.sendEvent(v, ev)
    assert win.index == 1


def test_zoom_and_fit(win, lib, qapp):
    win.open_any(lib["folder"])
    s0 = win.viewer.current_scale()
    win.act_zoom_in()
    assert win.viewer.current_scale() > s0
    win.act_fit_original()
    assert abs(win.viewer.current_scale() - 1.0) < 1e-6
    win.act_fit_width()
    assert win.viewer.fit_mode == "width"
    win.act_fit_window()


def test_click_navigation(win, lib, qapp):
    win.open_any(lib["folder"])
    v = win.viewer
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(v.width() - 20, v.height() // 2))
    pump(qapp, 700)
    assert win.index == 1
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(20, v.height() // 2))
    pump(qapp, 700)
    assert win.index == 0


def test_formats_folder_shows_error_page_without_crash(win, lib, qapp):
    win.open_any(lib["formats"])
    seen = []
    for _ in range(len(win.book)):
        seen.append((names(win)[0], win.viewer.pages[0].dec.error is None))
        win.act_next_single()
    ok = dict(seen)
    assert ok["g_broken.jpg"] is False
    assert all(v for k, v in ok.items() if k != "g_broken.jpg")


def test_side_click_is_immediate_and_double_click_center_fullscreen(win, lib, qapp):
    win.open_any(lib["folder"])
    v = win.viewer
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(v.width() - 10, 100))
    assert win.index == 1, "기다림 없이 바로 넘어감"
    QTest.mouseDClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(v.width() // 2, v.height() // 2))
    qapp.processEvents()
    assert win.isFullScreen()
    win.act_escape()
    qapp.processEvents()
    assert not win.isFullScreen()
