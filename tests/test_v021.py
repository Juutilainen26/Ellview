"""v0.2.1: [ ] / Ctrl+←→는 바로 옆 파일 첫 페이지, 휠·방향키는 넘어가지 않고 알림만."""
import json
import os

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.history import History


@pytest.fixture()
def win(qapp):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.resize(900, 700)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    w.viewer.setFocus()
    yield w
    w.close()


def base(w):
    return os.path.basename(w.book.path)


def wheel_down(v):
    ev = QWheelEvent(QPointF(100, 100), QPointF(v.mapToGlobal(QPoint(100, 100))), QPoint(0, 0), QPoint(0, -120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(v, ev)


def test_default_is_notify_only(win):
    assert win.s["boundary_action"] == "stop"


def test_arrow_and_wheel_never_change_file(win, lib):
    win.open_any(lib["folder"])
    win.act_last_page()
    for _ in range(3):
        QTest.keyClick(win, Qt.Key_Right)
        wheel_down(win.viewer)
        QTest.keyClick(win, Qt.Key_Space)
    QTest.mouseClick(win.viewer, Qt.LeftButton, Qt.NoModifier, QPoint(win.viewer.width() - 5, win.viewer.height() // 2))
    assert base(win) == "01_folder" and win.index == len(win.book) - 1
    t = win.viewer.toast.text()
    assert win.viewer.toast.isVisible() and "마지막 페이지" in t and "02_한글.zip" in t and "]" in t


def test_first_page_back_shows_notice(win, lib):
    win.open_any(lib["zip"])
    QTest.keyClick(win, Qt.Key_Left)
    QTest.keyClick(win, Qt.Key_Left)
    assert base(win) == "02_한글.zip" and win.index == 0
    assert "첫 페이지" in win.viewer.toast.text() and "01_folder" in win.viewer.toast.text()


def test_bracket_keys_open_first_page_both_ways(win, lib):
    win.open_any(lib["cbz"])
    win.show_index(2)
    QTest.keyClick(win, Qt.Key_BracketLeft)
    assert base(win) == "02_한글.zip" and win.index == 0, "[ 는 이전 파일 첫 페이지"
    win.show_index(2)
    QTest.keyClick(win, Qt.Key_BracketRight)
    assert base(win) == "03_comic.cbz" and win.index == 0, "] 는 다음 파일 첫 페이지 (이어보기 무시)"


def test_ctrl_arrows_open_first_page(win, lib):
    win.open_any(lib["cbz"])
    QTest.keyClick(win, Qt.Key_Left, Qt.ControlModifier)
    assert base(win) == "02_한글.zip" and win.index == 0
    QTest.keyClick(win, Qt.Key_Right, Qt.ControlModifier)
    QTest.keyClick(win, Qt.Key_Right, Qt.ControlModifier)
    assert base(win) == "04_seven.7z" and win.index == 0


def test_two_page_bracket_first_page(win, lib):
    win.act_toggle_two_page()
    win.open_any(lib["zip"])
    QTest.keyClick(win, Qt.Key_BracketLeft)
    assert base(win) == "01_folder" and win.spread[0] == 0


def test_no_neighbor_notice(win, lib):
    win.open_any(lib["rar"])
    win.act_last_page()
    win.act_next_page()
    assert "없어요" in win.viewer.toast.text()
    win.act_next_book()
    assert base(win) == "08_rar.cbr"


@pytest.mark.parametrize("stored,schema,expect", [
    ("prompt", 1, "stop"),   # 예전 기본값 → 새 기본값으로
    ("auto", 1, "auto"),     # 직접 고른 값은 유지
    ("prompt", 2, "prompt"), # 0.2.1 이후 직접 고른 값은 유지
])
def test_settings_migration(tmp_path, stored, schema, expect):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"schema": schema, "boundary_action": stored}), encoding="utf-8")
    s = Settings(p)
    assert s["boundary_action"] == expect and s["schema"] == 2


def test_settings_dialog_labels(win):
    from ellview.ui.dialogs import SettingsDialog
    dlg = SettingsDialog(win.s, win)
    assert dlg.boundary.currentData() == "stop" and not dlg.prev_start.isEnabled()
    dlg.boundary.setCurrentIndex(dlg.boundary.findData("prompt"))
    assert dlg.prev_start.isEnabled()
    dlg.close()
