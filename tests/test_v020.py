"""v0.2.0: 클릭 영역/화살표, 회전·반전, 복사, 슬라이드쇼, 탐색기 메뉴."""
import os
import time

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ellview.config import Settings
from ellview.core.bookmarks import BookmarkStore
from ellview.core.history import History


def make_win():
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.resize(1000, 700)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    w.viewer.setFocus()
    return w


@pytest.fixture()
def win(qapp):
    w = make_win()
    yield w
    w.close()


def pump(qapp, sec):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)


def hover(v, x, y=200):
    ev = QMouseEvent(QEvent.MouseMove, QPointF(x, y), v.mapToGlobal(QPointF(x, y)),
                     Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(v, ev)


# ------------------------------------------------------------------ 0. 클릭 영역
def test_zone_is_outer_fifth(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer
    w = v.width()
    assert v.zone_at(w * 0.19) == "left"
    assert v.zone_at(w * 0.21) is None
    assert v.zone_at(w * 0.5) is None
    assert v.zone_at(w * 0.79) is None
    assert v.zone_at(w * 0.81) == "right"


def test_click_inside_old_zone_no_longer_turns(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(int(v.width() * 0.3), 200))
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(int(v.width() * 0.7), 200))
    assert win.index == 0
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(int(v.width() * 0.9), 200))
    assert win.index == 1


def test_center_double_click_fullscreen_without_turning(win, lib, qapp):
    """후기: 더블클릭으로 전체 화면 하려다 페이지가 넘어감 → 가운데에서는 절대 안 넘어가야 함."""
    win.open_any(lib["folder"])
    v = win.viewer
    for x_ratio in (0.25, 0.5, 0.75):
        pt = QPoint(int(v.width() * x_ratio), v.height() // 2)
        QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.mouseDClick(v, Qt.LeftButton, Qt.NoModifier, pt)
        QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, pt)
        qapp.processEvents()
        assert win.index == 0, f"{x_ratio} 위치에서 넘어가면 안 됨"
        assert win.isFullScreen()
        win.act_escape()
        qapp.processEvents()


def test_hover_shows_arrow_and_hand_cursor(win, lib):
    win.open_any(lib["folder"])
    v = win.viewer
    hover(v, 10)
    assert v._hover_zone == "left" and v.cursor().shape() == Qt.PointingHandCursor
    hover(v, v.width() // 2)
    assert v._hover_zone is None and v.cursor().shape() != Qt.PointingHandCursor
    hover(v, v.width() - 10)
    assert v._hover_zone == "right"
    QApplication.sendEvent(v, QEvent(QEvent.Leave))
    assert v._hover_zone is None


def test_no_zone_without_pages_or_when_disabled(win, lib):
    v = win.viewer
    assert v.zone_at(5) is None
    win.open_any(lib["folder"])
    v.click_navigation = False
    assert v.zone_at(5) is None


def test_rtl_left_zone_is_next(win, lib):
    win.open_any(lib["folder"])
    win.act_toggle_rtl()
    v = win.viewer
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, QPoint(10, 200))
    assert win.index == 1


# ------------------------------------------------------------------ A. 회전/반전
@pytest.fixture()
def half_img_dir(tmp_path):
    d = tmp_path / "halves"
    d.mkdir()
    for i in range(3):
        im = Image.new("RGB", (400, 600), (255, 0, 0))
        im.paste((0, 0, 255), (200, 0, 400, 600))  # 왼쪽 빨강, 오른쪽 파랑
        im.save(d / f"{i + 1}.png")
    return str(d)


def test_rotation_persists_across_pages_and_books(win, lib, half_img_dir):
    win.open_any(half_img_dir)
    win.act_rotate_right()
    pg = win.viewer.pages[0]
    assert (pg.size.width(), pg.size.height()) == (600, 400)
    win.act_next_page()
    assert win.viewer.pages[0].rotation == 90, "다음 장에서도 유지"
    win.open_any(lib["zip"])
    assert win.viewer.pages[0].rotation == 90, "다른 파일에서도 유지"
    win.act_rotate_left()
    win.act_rotate_left()
    assert win.viewer.pages[0].rotation == 270
    assert "회전 270°" in win.status_label.text()
    win.act_reset_orientation()
    assert win.viewer.pages[0].rotation == 0


def test_flip_changes_pixels(win, half_img_dir):
    win.open_any(half_img_dir)
    img = win.viewer.pages[0].image()
    assert img.pixelColor(5, 5).red() > 200
    win.act_flip_h()
    img = win.viewer.pages[0].image()
    assert img.pixelColor(5, 5).blue() > 200 and img.pixelColor(5, 5).red() < 50
    win.act_next_page()
    assert win.viewer.pages[0].image().pixelColor(5, 5).blue() > 200, "다음 장에서도 반전 유지"
    assert win.actions["flip_h"].isChecked()


def test_orientation_resets_after_restart(qapp, half_img_dir):
    w = make_win()
    w.open_any(half_img_dir)
    w.act_rotate_right()
    w.act_flip_h()
    w.close()
    w2 = make_win()
    w2.open_any(half_img_dir)
    assert w2.viewer.pages[0].rotation == 0 and not w2.viewer.pages[0].flip
    assert "rotation" not in Settings().data and "flip" not in Settings().data
    w2.close()


def test_rotation_affects_two_page_layout(win, half_img_dir):
    win.s["cover_single"] = False
    win.open_any(half_img_dir)
    win.act_toggle_two_page()
    assert win.spread == [0, 1]
    win.act_rotate_right()  # 세로 → 가로가 되므로 단독 표시
    assert win.spread == [0]


def test_rotated_render_no_crash(win, lib, qapp):
    win.open_any(lib["folder"])
    win.act_last_page()  # GIF
    win.act_rotate_right()
    win.act_flip_h()
    pump(qapp, 0.3)
    assert not win.viewer.grab().isNull()


# ------------------------------------------------------------------ B. 복사
def test_copy_image_and_path(win, lib):
    win.open_any(lib["cbz"])
    win.act_copy_image()
    cb = QApplication.clipboard()
    assert cb.image().width() == 600
    win.act_copy_path()
    assert cb.text().endswith("03_comic.cbz > chapter/01.png")


def test_copy_rotated_image(win, half_img_dir):
    win.open_any(half_img_dir)
    win.act_rotate_right()
    win.act_copy_image()
    img = QApplication.clipboard().image()
    assert (img.width(), img.height()) == (600, 400)


# ------------------------------------------------------------------ C. 슬라이드쇼
def test_slideshow_advances_and_stops(win, lib, qapp):
    win.s["slideshow_interval"] = 0.2
    win.open_any(lib["folder"])
    win.act_toggle_slideshow()
    assert win.slide_timer.isActive() and win.actions["toggle_slideshow"].isChecked()
    pump(qapp, 0.55)
    assert win.index >= 2
    QTest.keyClick(win, Qt.Key_Escape)
    assert not win.slide_timer.isActive()


def test_slideshow_end_modes(win, lib, qapp):
    win.s["slideshow_interval"] = 0.2
    win.open_any(lib["tar"])  # 2장
    win.s["slideshow_end"] = "loop"
    win.act_last_page()
    win.act_toggle_slideshow()
    pump(qapp, 0.3)
    assert win.index == 0 and win.slide_timer.isActive()
    win._stop_slideshow()

    win.s["slideshow_end"] = "stop"
    win.act_last_page()
    win.act_toggle_slideshow()
    pump(qapp, 0.3)
    assert not win.slide_timer.isActive() and os.path.basename(win.book.path) == "05_tarball.tar.gz"

    win.s["slideshow_end"] = "next_book"
    win.act_last_page()
    win.act_toggle_slideshow()
    pump(qapp, 0.3)
    assert os.path.basename(win.book.path) == "07_formats" and win.slide_timer.isActive()
    win._stop_slideshow()


def test_slideshow_stops_at_last_file(win, lib, qapp):
    win.s["slideshow_interval"] = 0.2
    win.open_any(lib["rar"])
    win.act_last_page()
    win.act_toggle_slideshow()
    pump(qapp, 0.3)
    assert not win.slide_timer.isActive()


def test_slideshow_shortcut_s(win, lib):
    win.open_any(lib["folder"])
    QTest.keyClick(win, Qt.Key_S)
    assert win.slide_timer.isActive()
    QTest.keyClick(win, Qt.Key_S)
    assert not win.slide_timer.isActive()


# ------------------------------------------------------------------ E. 탐색기 메뉴
def test_shell_menu_plan():
    from ellview.core import shell_menu
    plan = shell_menu.plan()
    keys = [k for k, _v, _c in plan]
    assert keys[0].endswith(r"Directory\shell\Ellview")
    assert any(k.endswith(r"SystemFileAssociations\.cbz\shell\Ellview") for k in keys)
    assert any(k.endswith(r"SystemFileAssociations\.jpg\shell\Ellview") for k in keys)
    assert not any(r"\.gz\\" in k for k in keys)
    assert all(k.startswith("Software\\Classes\\") for k in keys), "HKCU 안의 Classes에만 씀"
    _k, values, cmd = plan[0]
    assert values["MUIVerb"] == "Ellview로 열기"
    assert cmd.endswith('"%1"') and "run.py" in cmd


@pytest.mark.skipif(os.name != "nt", reason="Windows 레지스트리 전용")
def test_shell_menu_register_roundtrip():
    from ellview.core import shell_menu
    try:
        n = shell_menu.register()
        assert n == len(shell_menu.key_paths())
        assert shell_menu.registered_command() == shell_menu.launch_command()[0]
        assert shell_menu.ensure_current() is False
    finally:
        shell_menu.unregister()
    assert shell_menu.registered_command() is None


def test_settings_dialog_new_fields(win):
    from ellview.ui.dialogs import SettingsDialog
    dlg = SettingsDialog(win.s, win)
    dlg.slide_iv.setValue(5.5)
    dlg.slide_end.setCurrentIndex(dlg.slide_end.findData("loop"))
    dlg._accept()
    s2 = Settings()
    assert s2["slideshow_interval"] == 5.5 and s2["slideshow_end"] == "loop"
    if os.name != "nt":
        assert not dlg.shell.isEnabled()


def test_new_actions_in_help_and_handlers(win):
    from ellview.ui.dialogs import shortcut_help_html
    html = shortcut_help_html({})
    for label in ("오른쪽으로 회전", "좌우 반전", "이미지 복사", "슬라이드쇼"):
        assert label in html
