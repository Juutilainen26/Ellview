"""5단계: 두 페이지/RTL, 설정, 단축키."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.history import History
from ellview.core.spread import last_start, prev_start, spread_at

WIDE = {3, 5}
wide = lambda i: i in WIDE  # noqa: E731


def test_spread_logic():
    n = 6
    seq, i = [], 0
    while i < n:
        s = spread_at(i, n, True, True, wide)
        seq.append(s)
        i = s[-1] + 1
    assert seq == [[0], [1, 2], [3], [4], [5]]
    assert prev_start(4, n, True, True, wide) == 3
    assert prev_start(3, n, True, True, wide) == 1
    assert prev_start(1, n, True, True, wide) == 0
    assert last_start(n, True, True, wide) == 5
    assert spread_at(0, n, True, False, lambda i: False) == [0, 1]
    assert last_start(4, True, False, lambda i: False) == 2
    assert spread_at(2, n, False, True, wide) == [2]


@pytest.fixture()
def win(qapp):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.resize(1100, 760)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    yield w
    w.close()


def test_two_page_navigation(win, lib):
    win.open_any(lib["folder"])
    win.act_toggle_two_page()
    seen = []
    for _ in range(5):
        seen.append(list(win.spread))
        win.act_next_page()
    assert seen == [[0], [1, 2], [3], [4], [5]]
    win.act_prev_page()
    assert win.spread == [4]
    win.act_prev_page()
    win.act_prev_page()
    assert win.spread == [1, 2]


def test_rtl_layout(win, lib):
    win.open_any(lib["folder"])
    win.act_toggle_two_page()
    win.act_next_page()
    rects = {p.name: r for p, r in win.viewer.page_rects()}
    assert rects["2.png"].x() < rects["3.jpg"].x()
    win.act_toggle_rtl()
    rects = {p.name: r for p, r in win.viewer.page_rects()}
    assert rects["2.png"].x() > rects["3.jpg"].x(), "RTL: 앞 페이지가 오른쪽"


def test_rtl_click_direction(win, lib, qapp):
    import time
    win.open_any(lib["folder"])
    win.act_toggle_rtl()
    v = win.viewer
    from PySide6.QtCore import QPoint
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(15, v.height() // 2))
    end = time.monotonic() + 0.7
    while time.monotonic() < end:
        qapp.processEvents()
    assert win.index == 1, "RTL에서는 왼쪽 클릭이 다음 페이지"


def test_settings_persist_and_shortcut_change(win, qapp, monkeypatch):
    from ellview.ui.dialogs import SettingsDialog
    dlg = SettingsDialog(win.s, win)
    # '다음 페이지' 단축키를 N으로 바꾸기
    for r in range(dlg.keys.rowCount()):
        if dlg.keys.item(r, 0).data(Qt.UserRole) == "next_page":
            dlg.keys.item(r, 2).setText("N, Right")
    dlg.boundary.setCurrentIndex(dlg.boundary.findData("auto"))
    dlg._accept()
    assert dlg.result() == 1
    win.reload_shortcuts()
    win.apply_settings()
    assert QKeySequence("N") in win.actions["next_page"].shortcuts()
    s2 = Settings()
    assert s2["boundary_action"] == "auto"
    assert s2["shortcuts"]["next_page"] == ["N", "Right"]


def test_duplicate_shortcut_rejected(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from ellview.ui.dialogs import SettingsDialog
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a)))
    dlg = SettingsDialog(win.s, win)
    for r in range(dlg.keys.rowCount()):
        if dlg.keys.item(r, 0).data(Qt.UserRole) == "prev_page":
            dlg.keys.item(r, 2).setText("Right")  # next_page와 중복
    dlg._accept()
    assert warned and dlg.result() == 0


def test_custom_shortcut_from_settings_file(qapp, lib):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    s["shortcuts"] = {"next_page": ["X"]}
    w = MainWindow(s, History(), BookmarkStore())
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    w.open_any(lib["folder"])
    QTest.keyClick(w, Qt.Key_X)
    assert w.index == 1
    QTest.keyClick(w, Qt.Key_Right)  # 기본 키는 더 이상 동작하지 않음
    assert w.index == 1
    w.close()


def test_fullscreen_toggle(win, lib, qapp):
    win.open_any(lib["folder"])
    win.act_toggle_fullscreen()
    qapp.processEvents()
    assert not win.menuBar().isVisible()
    win.act_escape()
    qapp.processEvents()
    assert win.menuBar().isVisible()


def test_info_overlay_and_status(win, lib):
    win.open_any(lib["folder"])
    win.act_toggle_info()
    assert "1.jpg" in win.viewer.info_text and "800×1150" in win.viewer.info_text
    assert "[1 / 6]" in win.status_label.text()
    win.act_toggle_info()
    assert win.viewer.info_text == ""


def test_dialogs_construct(win):
    from ellview.ui.dialogs import BookmarksDialog, HtmlDialog, about_html, shortcut_help_html
    BookmarksDialog(win.bookmarks, win).close()
    HtmlDialog("x", shortcut_help_html({}), win).close()
    HtmlDialog("x", about_html(), win).close()


def test_all_actions_have_handlers(win):
    from ellview.ui.shortcuts import ACTION_IDS
    missing = [a for a in ACTION_IDS if not hasattr(win, "act_" + a)]
    assert missing == []


def test_app_entry_smoke(lib, tmp_path):
    """실제 실행 진입점(run.py)을 별도 프로세스로 띄워 확인."""
    import json
    import os
    import subprocess
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", ELLVIEW_DATA_DIR=str(tmp_path / "smoke"))
    r = subprocess.run([sys.executable, os.path.join(root, "run.py"), lib["zip"], "--smoke-test"],
                       env=env, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode(errors="ignore")
    info = json.loads((tmp_path / "smoke" / "smoke.json").read_text(encoding="utf-8"))
    assert info["pages"] == 3 and info["first_ok"]
