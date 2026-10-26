"""테스트용 샘플 라이브러리 생성기."""
from __future__ import annotations

import io
import os
import tarfile
import zipfile

from PIL import Image, ImageDraw


def make_image(w, h, text, color, fmt="JPEG") -> bytes:
    im = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(im)
    d.rectangle([10, 10, w - 10, h - 10], outline=(255, 255, 255), width=6)
    d.text((w // 2 - 20, h // 2), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


def make_anim(fmt="GIF", frames=6, size=(240, 180)) -> bytes:
    ims = []
    for i in range(frames):
        im = Image.new("RGB", size, (40 * i % 255, 80, 200 - 25 * i))
        ImageDraw.Draw(im).ellipse([20 + i * 25, 50, 80 + i * 25, 110], fill=(255, 230, 0))
        ims.append(im)
    buf = io.BytesIO()
    kw = {"save_all": True, "append_images": ims[1:], "duration": 80, "loop": 0}
    ims[0].save(buf, fmt, **kw)
    return buf.getvalue()


def zip_with_cp949_names(path, files: dict[str, bytes]):
    """UTF-8 플래그 없이 CP949 파일명으로 저장된 zip(윈도우 한국어 환경의 흔한 형태)을 만든다."""
    placeholders = {}
    with zipfile.ZipFile(path, "w") as z:
        for i, (name, data) in enumerate(files.items()):
            raw = name.encode("cp949")
            ph = (f"P{i:03d}" + "x" * len(raw))[: len(raw)]
            assert len(ph) == len(raw)
            placeholders[ph.encode()] = raw
            z.writestr(ph, data)
    blob = open(path, "rb").read()
    for ph, raw in placeholders.items():
        blob = blob.replace(ph, raw)
    open(path, "wb").write(blob)


def build_library(root: str) -> dict:
    os.makedirs(root, exist_ok=True)
    out = {}
    # 1) 폴더 책
    a = os.path.join(root, "01_folder")
    os.makedirs(a, exist_ok=True)
    colors = [(200, 60, 60), (60, 160, 60), (60, 60, 200), (160, 120, 40), (120, 40, 160)]
    for i, c in enumerate(colors):
        fmt = "PNG" if i % 2 else "JPEG"
        ext = "png" if i % 2 else "jpg"
        w, h = (1200, 800) if i == 3 else (800, 1150)  # 4번째는 가로로 긴 이미지
        with open(os.path.join(a, f"{i + 1}.{ext}"), "wb") as f:
            f.write(make_image(w, h, f"A{i + 1}", c, fmt))
    with open(os.path.join(a, "10.gif"), "wb") as f:  # 자연 정렬 확인용 (10이 마지막)
        f.write(make_anim("GIF"))
    out["folder"] = a
    # 2) zip (cp949 이름)
    z = os.path.join(root, "02_한글.zip")
    zip_with_cp949_names(z, {f"그림{i}.jpg": make_image(700, 1000, f"Z{i}", (30 * i, 100, 150)) for i in range(1, 4)})
    out["zip"] = z
    # 3) cbz 하위 폴더 + __MACOSX 쓰레기
    c = os.path.join(root, "03_comic.cbz")
    with zipfile.ZipFile(c, "w") as zf:
        for i in range(1, 5):
            zf.writestr(f"chapter/{i:02d}.png", make_image(600, 900, f"C{i}", (90, 30 * i, 60), "PNG"))
        zf.writestr("__MACOSX/chapter/._01.png", b"junk")
        zf.writestr("readme.txt", b"hello")
    out["cbz"] = c
    # 4) 7z
    try:
        import py7zr
        s = os.path.join(root, "04_seven.7z")
        with py7zr.SevenZipFile(s, "w") as sz:
            for i in range(1, 4):
                sz.writestr(make_image(640, 900, f"S{i}", (20, 20 * i, 200)), f"s{i}.jpg")
        out["7z"] = s
    except ImportError:
        pass
    # 5) tar.gz
    t = os.path.join(root, "05_tarball.tar.gz")
    with tarfile.open(t, "w:gz") as tf:
        for i in range(1, 3):
            data = make_image(500, 700, f"T{i}", (200, 200, 30 * i))
            ti = tarfile.TarInfo(f"t{i}.jpg")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    out["tar"] = t
    # 6) 이미지 없는 폴더(건너뛰어야 함)
    os.makedirs(os.path.join(root, "06_empty"), exist_ok=True)
    # 7) 포맷 모음
    f = os.path.join(root, "07_formats")
    os.makedirs(f, exist_ok=True)
    with open(os.path.join(f, "a_anim.webp"), "wb") as fp:
        fp.write(make_anim("WEBP"))
    with open(os.path.join(f, "b_anim.png"), "wb") as fp:  # APNG
        fp.write(make_anim("PNG"))
    with open(os.path.join(f, "c.bmp"), "wb") as fp:
        fp.write(make_image(300, 300, "BMP", (10, 120, 120), "BMP"))
    with open(os.path.join(f, "d.tiff"), "wb") as fp:
        fp.write(make_image(300, 300, "TIF", (120, 10, 120), "TIFF"))
    try:
        with open(os.path.join(f, "e.avif"), "wb") as fp:
            fp.write(make_image(320, 240, "AVIF", (200, 100, 0), "AVIF"))
    except Exception:
        pass
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        with open(os.path.join(f, "f.heic"), "wb") as fp:
            fp.write(make_image(320, 240, "HEIC", (0, 100, 200), "HEIF"))
    except Exception:
        pass
    with open(os.path.join(f, "g_broken.jpg"), "wb") as fp:
        fp.write(b"\xff\xd8\xff\xe0not really a jpeg")
    out["formats"] = f
    return out
