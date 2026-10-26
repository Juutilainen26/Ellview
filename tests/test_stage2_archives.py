"""2단계: 압축파일."""
import os
import zipfile

import pytest

from ellview.core.archives import PasswordRequired, open_archive
from ellview.core.books import ArchiveBook, open_path
from ellview.core.loader import ImageCache, PageLoader, decode


def test_zip_cp949_names(lib):
    b = ArchiveBook(lib["zip"])
    assert [p.name for p in b.pages] == ["그림1.jpg", "그림2.jpg", "그림3.jpg"]
    assert b.read(0)[:2] == b"\xff\xd8"


def test_cbz_subfolder_and_junk_filtered(lib):
    b = ArchiveBook(lib["cbz"])
    assert [p.name for p in b.pages] == [f"chapter/{i:02d}.png" for i in range(1, 5)]


def test_7z(lib, qapp):
    if "7z" not in lib:
        pytest.skip("py7zr 없음")
    b = ArchiveBook(lib["7z"])
    assert [p.name for p in b.pages] == ["s1.jpg", "s2.jpg", "s3.jpg"]
    d = decode(b.read(2), b.pages[2].name)
    assert d.error is None and d.image.width() == 640


def test_tar_gz(lib):
    b, start = open_path(lib["tar"])
    assert b.kind == "archive" and start is None
    assert [p.name for p in b.pages] == ["t1.jpg", "t2.jpg"]
    assert len(b.read(1)) > 100


def test_rar_natural_order(lib):
    b = ArchiveBook(lib["rar"])
    assert [p.name for p in b.pages] == ["r/01.jpg", "r/02.jpg", "r/03.jpg", "r/10.jpg"]
    assert b.read(0)[:2] == b"\xff\xd8"


def test_wrong_extension_detected(lib, tmp_path):
    fake = tmp_path / "actually_zip.cbr"
    fake.write_bytes(open(lib["cbz"], "rb").read())
    b = ArchiveBook(str(fake))
    assert len(b) == 4


def test_encrypted_zip_requires_password(tmp_path):
    # zipfile은 암호화 zip을 쓸 수 없어서, 플래그만 켠 zip으로 감지 경로를 확인
    p = tmp_path / "enc.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("a.jpg", b"x" * 100)
    data = bytearray(p.read_bytes())
    # local header와 central directory의 general purpose flag 비트0(암호화) 설정
    lh = data.find(b"PK\x03\x04")
    data[lh + 6] |= 0x01
    cd = data.find(b"PK\x01\x02")
    data[cd + 8] |= 0x01
    p.write_bytes(bytes(data))
    a = open_archive(str(p))
    with pytest.raises(PasswordRequired):
        a.read("a.jpg")


def test_prefetch_fills_cache(lib, qapp):
    b = ArchiveBook(lib["cbz"])
    cache = ImageCache(256)
    ld = PageLoader(cache)
    ld.set_book(b)
    ld.prefetch([1, 2, 3])
    ld.wait()
    qapp.processEvents()
    assert all(ld.cached(i) is not None for i in (1, 2, 3))


def test_gui_opens_each_archive(qapp, lib, tmp_path):
    from ellview.config import Settings
    from ellview.core.bookmarks import BookmarkStore
    from ellview.core.history import History
    from ellview.ui.main_window import MainWindow
    s = Settings()
    s["check_updates"] = False
    w = MainWindow(s, History(), BookmarkStore())
    w.show()
    for key in ("zip", "cbz", "7z", "tar", "rar"):
        if key not in lib:
            continue
        assert w.open_any(lib[key]), key
        assert w.viewer.pages and w.viewer.pages[0].dec.error is None, key
    w.close()
