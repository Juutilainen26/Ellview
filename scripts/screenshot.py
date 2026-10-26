"""개발용: 오프스크린으로 창을 띄워 여러 상태의 스크린샷을 screenshots/에 저장.

사용: python scripts/screenshot.py
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ["ELLVIEW_DATA_DIR"] = tempfile.mkdtemp()

from PySide6.QtWidgets import QApplication  # noqa: E402

from samples import build_library  # noqa: E402


def pump(app, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main():
    app = QApplication([])
    from ellview.config import Settings
    from ellview.ui.main_window import MainWindow
    from ellview.ui.theme import apply_theme
    out = os.path.join(ROOT, "screenshots")
    os.makedirs(out, exist_ok=True)
    lib = build_library(os.path.join(tempfile.mkdtemp(), "lib"))
    s = Settings()
    s["check_updates"] = False
    apply_theme(app, s["theme"])
    w = MainWindow(s)
    w.resize(1100, 780)
    w.show()
    pump(app, 200)

    def shot(name):
        pump(app, 250)
        w.grab().save(os.path.join(out, name + ".png"))

    shot("00_empty")
    w.open_any(lib["folder"])
    shot("01_folder_first")
    w.act_last_page()
    shot("02_gif")
    w.open_any(lib["zip"])
    shot("03_zip_cp949")
    w.open_any(lib["folder"])
    w.act_toggle_two_page()
    w.act_first_page()
    w.act_next_page()
    shot("04_two_page")
    w.act_toggle_rtl()
    shot("05_two_page_rtl")
    w.act_toggle_rtl()
    w.act_toggle_two_page()
    w.act_toggle_thumbnails()
    w.act_toggle_info()
    shot("06_thumbs_info")
    w.act_toggle_info()
    w.act_last_page()
    w.act_next_page()
    shot("07_boundary_prompt")
    w.act_next_page()
    shot("08_next_book")
    w.act_fit_width()
    shot("09_fit_width")
    w.act_fit_window()
    from ellview.core.bookmarks import Bookmark
    w.bookmarks.add(Bookmark.from_book(w.book, 0, "샘플 책갈피"))
    from ellview.ui.dialogs import BookmarksDialog, HtmlDialog, SettingsDialog, shortcut_help_html
    for name, dlg in (("10_bookmarks", BookmarksDialog(w.bookmarks, w)),
                      ("11_settings", SettingsDialog(w.s, w)),
                      ("12_help", HtmlDialog("단축키", shortcut_help_html({}), w))):
        dlg.show()
        pump(app, 200)
        dlg.grab().save(os.path.join(out, name + ".png"))
        dlg.close()
    w.close()


if __name__ == "__main__":
    main()
