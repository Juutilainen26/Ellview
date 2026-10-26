"""책갈피.

경로(절대경로) + 페이지 이름을 기본으로 저장하고, 파일을 옮겼을 때를 대비해
책 이름·크기·지문(fingerprint)도 함께 저장합니다.
경로에서 못 찾으면 '라이브러리 폴더'와 원래 경로의 상위 폴더를 뒤져서
같은 지문의 파일/폴더를 찾아 책갈피 경로를 자동으로 고쳐 줍니다.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ellview.config import data_dir, load_json, save_json
from ellview.core.formats import is_archive_name, is_image_name, natural_key

_CHUNK = 64 * 1024


def file_fingerprint(path: str) -> str:
    """파일 크기 + 앞/뒤 64KB 해시. 이름을 바꾸거나 옮겨도 같은 값."""
    st = os.stat(path)
    h = hashlib.sha1(str(st.st_size).encode())
    with open(path, "rb") as f:
        h.update(f.read(_CHUNK))
        if st.st_size > _CHUNK * 2:
            f.seek(-_CHUNK, os.SEEK_END)
            h.update(f.read(_CHUNK))
    return h.hexdigest()[:20]


def names_fingerprint(names) -> str:
    imgs = sorted((n for n in names if is_image_name(n)), key=natural_key)
    h = hashlib.sha1("\n".join(imgs).encode("utf-8", "surrogatepass"))
    return h.hexdigest()[:20]


def folder_fingerprint(path: str) -> str:
    try:
        return names_fingerprint(os.listdir(path))
    except OSError:
        return ""


@dataclass
class Bookmark:
    book_path: str
    book_kind: str           # folder | archive
    page_name: str
    page_index: int
    page_count: int = 0
    title: str = ""
    book_name: str = ""
    book_size: int = -1
    fingerprint: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    @property
    def location(self) -> str:
        """경로 형식 표시."""
        if self.book_kind == "folder":
            return os.path.join(self.book_path, self.page_name)
        return f"{self.book_path} > {self.page_name}"

    @classmethod
    def from_book(cls, book, index: int, title: str = "") -> "Bookmark":
        kind = book.kind
        size = -1
        fp = ""
        try:
            if kind == "archive":
                size = os.path.getsize(book.path)
                fp = file_fingerprint(book.path)
            else:
                fp = names_fingerprint(p.name for p in book.pages)
        except OSError:
            pass
        page = book.pages[index] if book.pages else None
        return cls(book_path=book.path, book_kind=kind,
                   page_name=page.name if page else "", page_index=index,
                   page_count=len(book), title=title or f"{book.title} - {index + 1}p",
                   book_name=os.path.basename(book.path.rstrip("\\/")), book_size=size, fingerprint=fp)


def _search_roots(bm: Bookmark, extra_roots) -> list[str]:
    roots = []
    for r in extra_roots or []:
        if r and os.path.isdir(r):
            roots.append(os.path.abspath(r))
    # 원래 경로에서 존재하는 가장 가까운 상위 폴더 (한 단계 더 위까지)
    p = os.path.dirname(os.path.abspath(bm.book_path).rstrip("\\/"))
    while p and not os.path.isdir(p):
        np_ = os.path.dirname(p)
        if np_ == p:
            break
        p = np_
    if p and os.path.isdir(p):
        roots.append(p)
        up = os.path.dirname(p)
        if up and up != p and os.path.isdir(up) and os.path.dirname(up) != up:
            roots.append(up)
    seen, out = set(), []
    for r in roots:
        k = os.path.normcase(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _depth(root: str, path: str) -> int:
    rel = os.path.relpath(path, root)
    return 0 if rel == "." else rel.count(os.sep) + 1


def relocate(bm: Bookmark, extra_roots=None, max_depth: int = 6,
             time_limit: float = 10.0) -> tuple[str | None, bool]:
    """책갈피의 책을 찾아 (경로, 확실한지)를 돌려줍니다.
    확실함 = 원래 경로에 있거나 지문이 일치. 이름만 같은 후보는 확실하지 않음(False)으로 돌려줘서
    UI에서 사용자에게 확인받게 합니다. 못 찾으면 (None, False)."""
    if bm.book_kind == "archive" and os.path.isfile(bm.book_path):
        return bm.book_path, True
    if bm.book_kind == "folder" and os.path.isdir(bm.book_path):
        return bm.book_path, True

    deadline = time.monotonic() + time_limit
    name_low = bm.book_name.lower()
    fp_only = None      # 지문은 같지만 이름이 바뀐 경우
    name_only = None    # 이름만 같은 경우(재압축 등) - 최후 후보
    for root in _search_roots(bm, extra_roots):
        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() > deadline:
                return _result(fp_only, name_only)
            if _depth(root, dirpath) >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if not d.startswith(("$", ".")) and d != "System Volume Information"]
            if bm.book_kind == "archive":
                for fn in filenames:
                    if not is_archive_name(fn):
                        continue
                    full = os.path.join(dirpath, fn)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        continue
                    if size == bm.book_size:
                        try:
                            fp = file_fingerprint(full)
                        except OSError:
                            continue
                        if fp == bm.fingerprint:
                            if fn.lower() == name_low:
                                return full, True
                            fp_only = fp_only or full
                    elif fn.lower() == name_low and name_only is None:
                        name_only = full
            else:
                base = os.path.basename(dirpath)
                if any(is_image_name(f) for f in filenames):
                    fp = names_fingerprint(filenames)
                    if fp == bm.fingerprint:
                        if base.lower() == name_low:
                            return dirpath, True
                        fp_only = fp_only or dirpath
                    elif base.lower() == name_low and name_only is None:
                        name_only = dirpath
    return _result(fp_only, name_only)


def _result(fp_only, name_only):
    if fp_only:
        return fp_only, True
    if name_only:
        return name_only, False
    return None, False


class BookmarkStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "bookmarks.json")
        raw = load_json(self.path, {})
        items = raw.get("bookmarks", []) if isinstance(raw, dict) else []
        self.items: list[Bookmark] = []
        fields = set(Bookmark.__dataclass_fields__)
        for d in items:
            try:
                self.items.append(Bookmark(**{k: v for k, v in d.items() if k in fields}))
            except TypeError:
                continue

    def add(self, bm: Bookmark) -> Bookmark:
        self.items.insert(0, bm)
        self.save()
        return bm

    def remove(self, bm_id: str):
        self.items = [b for b in self.items if b.id != bm_id]
        self.save()

    def get(self, bm_id: str) -> Bookmark | None:
        return next((b for b in self.items if b.id == bm_id), None)

    def update_path(self, bm: Bookmark, new_path: str):
        bm.book_path = os.path.abspath(new_path)
        bm.book_name = os.path.basename(bm.book_path.rstrip("\\/"))
        bm.updated = time.time()
        self.save()

    def save(self):
        save_json(self.path, {"version": 1, "bookmarks": [asdict(b) for b in self.items]})
