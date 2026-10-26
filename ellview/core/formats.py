"""지원 확장자 목록과 자연 정렬."""
from __future__ import annotations

import re

# 정적/애니메이션 이미지 (Qt 또는 Pillow로 디코딩)
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".gif", ".webp", ".bmp", ".dib",
    ".tif", ".tiff", ".ico", ".tga", ".psd", ".avif", ".heic", ".heif", ".jxl",
    ".pcx", ".ppm", ".pgm", ".pbm", ".dds", ".svg", ".qoi",
}

# 애니메이션 가능성이 있는 확장자
ANIM_EXTS = {".gif", ".webp", ".png", ".apng", ".avif"}

# 압축 확장자 → 백엔드 이름 (archives.py에 등록된 이름)
ARCHIVE_EXTS = {
    ".zip": "zip", ".cbz": "zip",
    ".7z": "7z", ".cb7": "7z",
    ".rar": "rar", ".cbr": "rar",
    ".tar": "tar", ".cbt": "tar", ".tgz": "tar", ".gz": "tar", ".bz2": "tar", ".xz": "tar",
}


def ext_of(name: str) -> str:
    n = name.lower()
    for multi in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if n.endswith(multi):
            return ".tgz"
    i = n.rfind(".")
    return n[i:] if i >= 0 else ""


def is_image_name(name: str) -> bool:
    return ext_of(name) in IMAGE_EXTS


def is_archive_name(name: str) -> bool:
    e = ext_of(name)
    if e in (".gz", ".bz2", ".xz"):
        # 단독 .gz 등은 tar가 아닐 수 있으므로 .tar.* 형태만 인정
        return False
    return e in ARCHIVE_EXTS


def archive_backend_for(name: str) -> str | None:
    e = ext_of(name)
    if e in (".gz", ".bz2", ".xz"):
        return None
    return ARCHIVE_EXTS.get(e)


_num_re = re.compile(r"(\d+)")


def natural_key(s: str):
    """'2.jpg' < '10.jpg' 처럼 사람이 기대하는 순서로 정렬하는 키."""
    s = s.replace("\\", "/").lower()
    parts = _num_re.split(s)
    key = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p), p))
        else:
            key.append((1, 0, p))
    return key
