"""4단계: 책갈피 재탐색, 이어보기, 최근 파일."""
import os
import shutil

import pytest

from ellview.config import Settings
from ellview.core.bookmarks import Bookmark, BookmarkStore, relocate
from ellview.core.books import ArchiveBook, FolderBook
from ellview.core.history import History


def bm_for(path, index, kind="archive"):
    book = ArchiveBook(path) if kind == "archive" else FolderBook(path)
    bm = Bookmark.from_book(book, index)
    book.close()
    return bm


def test_existing_path(lib):
    bm = bm_for(lib["cbz"], 2)
    assert relocate(bm) == (lib["cbz"], True)
    assert bm.location.endswith("03_comic.cbz > chapter/03.png")


def test_moved_into_subfolder(lib):
    bm = bm_for(lib["cbz"], 2)
    root = os.path.dirname(lib["cbz"])
    new = os.path.join(root, "정리", "만화", "03_comic.cbz")
    os.makedirs(os.path.dirname(new))
    shutil.move(lib["cbz"], new)
    assert relocate(bm) == (new, True)


def test_moved_and_renamed(lib):
    bm = bm_for(lib["cbz"], 1)
    root = os.path.dirname(lib["cbz"])
    new = os.path.join(root, "sub", "renamed_comic.cbz")
    os.makedirs(os.path.dirname(new))
    shutil.move(lib["cbz"], new)
    assert relocate(bm) == (new, True)


def test_folder_moved_and_renamed(lib):
    bm = bm_for(lib["folder"], 3, "folder")
    root = os.path.dirname(lib["folder"])
    new = os.path.join(root, "x", "새이름")
    os.makedirs(os.path.dirname(new))
    shutil.move(lib["folder"], new)
    assert relocate(bm) == (new, True)


def test_library_root_search(lib, tmp_path):
    bm = bm_for(lib["zip"], 0)
    import pathlib
    import tempfile
    drive = pathlib.Path(tempfile.mkdtemp(prefix="ellview_other_"))  # 원래 위치와 무관한 별도 트리
    other = drive / "D_drive" / "만화" / "깊은" / "폴더"
    other.mkdir(parents=True)
    # 원래 상위 폴더 자체를 없애서 상위 폴더 탐색으로는 못 찾게 함
    new = other / "02_한글.zip"
    shutil.move(lib["zip"], new)
    shutil.rmtree(os.path.dirname(lib["zip"]))
    assert relocate(bm)[0] != str(new)  # 라이브러리 폴더 없이는 새 위치를 못 찾음
    assert relocate(bm, [str(drive / "D_drive")]) == (str(new), True)
    shutil.rmtree(drive)


def test_name_only_is_uncertain(lib):
    bm = bm_for(lib["cbz"], 0)
    root = os.path.dirname(lib["cbz"])
    os.remove(lib["cbz"])
    os.makedirs(os.path.join(root, "other"))
    with open(os.path.join(root, "other", "03_comic.cbz"), "wb") as f:
        f.write(b"PK\x05\x06" + b"\x00" * 18)
    path, sure = relocate(bm)
    assert path.endswith(os.path.join("other", "03_comic.cbz")) and sure is False


def test_not_found(lib):
    bm = bm_for(lib["cbz"], 0)
    os.remove(lib["cbz"])
    assert relocate(bm) == (None, False)


def test_store_roundtrip(lib, tmp_path):
    st = BookmarkStore(tmp_path / "bm.json")
    st.add(bm_for(lib["cbz"], 2))
    st2 = BookmarkStore(tmp_path / "bm.json")
    assert len(st2.items) == 1 and st2.items[0].page_name == "chapter/03.png"
    st2.remove(st2.items[0].id)
    assert BookmarkStore(tmp_path / "bm.json").items == []


def test_history_recent_and_positions(tmp_path):
    h = History(tmp_path / "h.json")
    h.add_recent("/a/1.zip")
    h.add_recent("/a/2.zip")
    h.add_recent("/a/1.zip")
    assert [os.path.basename(p) for p in h.recent()] == ["1.zip", "2.zip"]
    h.set_position("/a/1.zip", 5, "06.jpg", 20)
    h.save()
    h2 = History(tmp_path / "h.json")
    assert h2.get_position("/a/1.zip")["index"] == 5


# ------------------------------------------------------------------ GUI
@pytest.fixture()
def win(qapp):
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.show()
    yield w
    w.close()


def test_gui_bookmark_after_move(win, lib, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("내 책갈피", True)))
    win.open_any(lib["cbz"])
    win.show_index(2)
    win.act_add_bookmark()
    bm = win.bookmarks.items[0]
    assert bm.title == "내 책갈피"
    win.act_close_book()
    root = os.path.dirname(lib["cbz"])
    new = os.path.join(root, "moved", "03_comic.cbz")
    os.makedirs(os.path.dirname(new))
    shutil.move(lib["cbz"], new)
    assert win.open_bookmark(bm.id)
    assert os.path.normcase(win.book.path) == os.path.normcase(new)
    assert win.index == 2
    assert BookmarkStore().items[0].book_path == os.path.abspath(new), "옮긴 경로가 저장됨"


def test_gui_resume(win, lib):
    win.open_any(lib["folder"])
    win.show_index(3)
    win.open_any(lib["zip"])
    win.open_any(lib["folder"])
    assert win.index == 3
    assert "이어서" in win.viewer.toast.text()
    win.close()
    # 프로그램 재시작 후에도 유지
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w2 = MainWindow(s, History(), BookmarkStore())
    w2.open_any(lib["folder"])
    assert w2.index == 3
    assert os.path.basename(w2.history.recent()[0]) == "01_folder"
    w2.close()


def test_gui_resume_disabled(win, lib):
    win.s["resume_last_page"] = False
    win.open_any(lib["folder"])
    win.show_index(3)
    win.open_any(lib["zip"])
    win.open_any(lib["folder"])
    assert win.index == 0


def test_opening_image_file_ignores_resume(win, lib):
    win.open_any(lib["folder"])
    win.show_index(4)
    win.open_any(lib["zip"])
    win.open_any(os.path.join(lib["folder"], "2.png"))
    assert win.index == 1
