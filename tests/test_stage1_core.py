"""1단계: 디코딩, 자연 정렬, 폴더 책, 대용량."""
import io
import os

from PIL import Image

from ellview.core.books import FolderBook, open_path
from ellview.core.formats import natural_key
from ellview.core.loader import ImageCache, decode


def test_natural_sort():
    names = ["10.jpg", "2.jpg", "1.jpg", "img20.png", "img3.png"]
    assert sorted(names, key=natural_key) == ["1.jpg", "2.jpg", "10.jpg", "img3.png", "img20.png"]


def test_folder_book_order(lib):
    b = FolderBook(lib["folder"])
    assert [p.name for p in b.pages] == ["1.jpg", "2.png", "3.jpg", "4.png", "5.jpg", "10.gif"]


def test_open_image_starts_at_that_image(lib):
    book, start = open_path(os.path.join(lib["folder"], "3.jpg"))
    assert book.kind == "folder" and start == 2


def test_decode_formats(qapp, lib):
    f = lib["formats"]
    results = {}
    for name in sorted(os.listdir(f)):
        with open(os.path.join(f, name), "rb") as fp:
            d = decode(fp.read(), name)
        results[name] = d
    assert results["a_anim.webp"].animated
    assert results["b_anim.png"].animated, "APNG 애니메이션 감지"
    assert not results["c.bmp"].animated and not results["c.bmp"].image.isNull()
    assert not results["d.tiff"].image.isNull()
    if "e.avif" in results:
        assert not results["e.avif"].image.isNull(), results["e.avif"].error
    if "f.heic" in results:
        assert not results["f.heic"].image.isNull(), results["f.heic"].error
    assert results["g_broken.jpg"].error is not None


def test_gif_animated(qapp, lib):
    with open(os.path.join(lib["folder"], "10.gif"), "rb") as fp:
        d = decode(fp.read(), "10.gif")
    assert d.animated and d.data


def test_large_image_downscaled(qapp):
    im = Image.new("RGB", (12000, 9000), (10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=50)
    d = decode(buf.getvalue(), "big.jpg", max_megapixels=40)
    assert d.downscaled
    assert d.orig_size.width() == 12000
    assert d.image.width() * d.image.height() <= 40_000_000 * 1.01


def test_exif_orientation(qapp):
    im = Image.new("RGB", (400, 200), (255, 0, 0))
    exif = im.getexif()
    exif[0x0112] = 6  # 90도 회전
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    d = decode(buf.getvalue(), "rot.jpg")
    assert d.image.width() == 200 and d.image.height() == 400


def test_cache_budget(qapp):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage
    from ellview.core.loader import Decoded
    c = ImageCache(budget_mb=1)
    for i in range(5):
        img = QImage(400, 400, QImage.Format_RGB32)  # 640KB
        c.put(("b", i), Decoded(img, QSize(400, 400), "png", 1))
    assert c.used <= 1024 * 1024 + 700_000
    assert c.get(("b", 4)) is not None
