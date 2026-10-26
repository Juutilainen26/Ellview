"""3단계: 처음/끝에서 파일 이동."""
import os
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.books import neighbor_book
from ellview.core.history import History


@pytest.fixture()
def win(qapp):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    s["boundary_action"] = "prompt"  # 이 파일은 '안내 후 이동' 모드를 검사 (0.2.1부터 기본값은 stop)
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


def test_neighbor_skips_empty_folder(lib):
    root = os.path.dirname(lib["folder"])
    assert os.path.basename(neighbor_book(lib["tar"], +1)) == "07_formats"
    assert os.path.basename(neighbor_book(os.path.join(root, "07_formats"), -1)) == "05_tarball.tar.gz"
    assert neighbor_book(lib["rar"], +1) is None
    assert neighbor_book(lib["folder"], -1) is None


def test_prompt_then_move(win, lib):
    win.open_any(lib["folder"])
    win.act_last_page()
    win.act_next_page()
    assert base(win) == "01_folder", "첫 번째 넘김에선 이동하지 않고 안내만"
    assert win.viewer.toast.isVisible() and "02_한글.zip" in win.viewer.toast.text()
    win.act_next_page()
    assert base(win) == "02_한글.zip" and win.index == 0


def test_enter_confirms(win, lib):
    win.open_any(lib["folder"])
    win.act_last_page()
    win.act_next_page()
    QTest.keyClick(win, Qt.Key_Return)
    assert base(win) == "02_한글.zip"


def test_escape_cancels_prompt(win, lib):
    win.open_any(lib["folder"])
    win.act_last_page()
    win.act_next_page()
    QTest.keyClick(win, Qt.Key_Escape)
    assert win._boundary is None
    win.act_next_page()  # 다시 안내부터
    assert base(win) == "01_folder"


def test_prev_book_starts_at_last_page(win, lib):
    win.open_any(lib["zip"])
    win.act_prev_page()
    win.act_prev_page()
    assert base(win) == "01_folder"
    assert win.index == len(win.book) - 1


def test_prompt_expires(win, lib, monkeypatch):
    import ellview.ui.main_window as mw
    monkeypatch.setattr(mw, "BOUNDARY_TIMEOUT", 0.05)
    win.open_any(lib["folder"])
    win.act_last_page()
    win.act_next_page()
    time.sleep(0.1)
    win.act_next_page()
    assert base(win) == "01_folder"


def test_auto_and_stop_modes(win, lib):
    win.s["boundary_action"] = "auto"
    win.open_any(lib["folder"])
    win.act_last_page()
    win.act_next_page()
    assert base(win) == "02_한글.zip"
    win.s["boundary_action"] = "stop"
    win.act_last_page()
    win.act_next_page()
    win.act_next_page()
    assert base(win) == "02_한글.zip"


def test_no_more_files(win, lib):
    win.open_any(lib["rar"])
    win.act_last_page()
    win.act_next_page()
    assert "없어요" in win.viewer.toast.text()
    win.act_next_page()
    assert base(win) == "08_rar.cbr"


def test_next_book_shortcuts(win, lib):
    win.open_any(lib["folder"])
    QTest.keyClick(win, Qt.Key_Right, Qt.ControlModifier)
    assert base(win) == "02_한글.zip"
    QTest.keyClick(win, Qt.Key_BracketRight)
    assert base(win) == "03_comic.cbz"
    QTest.keyClick(win, Qt.Key_BracketLeft)
    assert base(win) == "02_한글.zip"


def test_skip_empty_folder_in_gui(win, lib):
    win.open_any(lib["tar"])
    win.act_next_book()
    assert base(win) == "07_formats"


def test_open_parent_folder_opens_first_child(win, lib):
    root = os.path.dirname(lib["folder"])
    assert win.open_any(root)
    assert base(win) == "01_folder"
