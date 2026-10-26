"""'책' 단위 추상화: 폴더 하나 또는 압축파일 하나가 한 권의 책입니다.

페이지 이동은 책 안에서, 파일 이동(다음/이전 파일)은 같은 부모 폴더의 형제 책 사이에서 일어납니다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ellview.core.archives import ArchiveBackend, open_archive
from ellview.core.formats import is_archive_name, is_image_name, natural_key


@dataclass
class Page:
    name: str          # 폴더: 파일명 / 압축: 내부 경로
    size: int = -1     # 알 수 있으면 바이트 크기

    @property
    def display_name(self) -> str:
        return self.name.replace("\\", "/").rsplit("/", 1)[-1]


class Book:
    kind = "base"

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.pages: list[Page] = []

    @property
    def title(self) -> str:
        return os.path.basename(self.path.rstrip("\\/")) or self.path

    def __len__(self):
        return len(self.pages)

    def read(self, index: int) -> bytes:
        raise NotImplementedError

    def index_of(self, name: str) -> int:
        for i, p in enumerate(self.pages):
            if p.name == name:
                return i
        low = name.replace("\\", "/").lower()
        for i, p in enumerate(self.pages):
            if p.name.replace("\\", "/").lower() == low:
                return i
        return -1

    def page_location(self, index: int) -> str:
        """사람이 읽을 수 있는 경로 형식."""
        if not self.pages:
            return self.path
        name = self.pages[index].name
        if self.kind == "folder":
            return os.path.join(self.path, name)
        return f"{self.path} > {name}"

    def close(self):
        pass


class FolderBook(Book):
    kind = "folder"

    def __init__(self, path: str):
        super().__init__(path)
        entries = []
        try:
            with os.scandir(self.path) as it:
                for e in it:
                    try:
                        if e.is_file() and is_image_name(e.name):
                            entries.append(Page(e.name, e.stat().st_size))
                    except OSError:
                        continue
        except OSError:
            pass
        entries.sort(key=lambda p: natural_key(p.name))
        self.pages = entries

    def read(self, index: int) -> bytes:
        with open(os.path.join(self.path, self.pages[index].name), "rb") as f:
            return f.read()


class ArchiveBook(Book):
    kind = "archive"

    def __init__(self, path: str, password: str | None = None):
        super().__init__(path)
        self.backend: ArchiveBackend = open_archive(self.path, password)
        names = sorted(self.backend.names(), key=natural_key)
        self.pages = [Page(n) for n in names]

    def read(self, index: int) -> bytes:
        return self.backend.read(self.pages[index].name)

    def close(self):
        try:
            self.backend.close()
        except Exception:
            pass


def is_book_path(path: str) -> bool:
    if os.path.isdir(path):
        return True
    return os.path.isfile(path) and is_archive_name(path)


def folder_has_images(path: str) -> bool:
    try:
        with os.scandir(path) as it:
            for e in it:
                if is_image_name(e.name) and e.is_file():
                    return True
    except OSError:
        pass
    return False


def open_path(path: str, password: str | None = None) -> tuple[Book, int | None]:
    """경로를 열어 (책, 시작 페이지)를 돌려줍니다. 시작 페이지가 None이면 '이어보기' 대상."""
    path = os.path.abspath(path)
    if os.path.isdir(path):
        return FolderBook(path), None
    if is_archive_name(path):
        return ArchiveBook(path, password), None
    if is_image_name(path):
        book = FolderBook(os.path.dirname(path))
        idx = book.index_of(os.path.basename(path))
        return book, max(idx, 0)
    raise ValueError("지원하지 않는 파일입니다: " + path)


def sibling_books(book_path: str) -> list[str]:
    """같은 부모 폴더의 책 후보(하위 폴더 + 압축파일)를 자연 정렬 순서로."""
    parent = os.path.dirname(os.path.abspath(book_path).rstrip("\\/"))
    out = []
    try:
        with os.scandir(parent) as it:
            for e in it:
                try:
                    if e.is_dir():
                        out.append(e.path)
                    elif e.is_file() and is_archive_name(e.name):
                        out.append(e.path)
                except OSError:
                    continue
    except OSError:
        return [os.path.abspath(book_path)]
    out.sort(key=lambda p: natural_key(os.path.basename(p)))
    return out


def neighbor_book(book_path: str, step: int) -> str | None:
    """step=+1 다음 책, -1 이전 책. 이미지가 없는 폴더는 건너뜁니다."""
    book_path = os.path.abspath(book_path)
    sibs = sibling_books(book_path)
    norm = [os.path.normcase(p) for p in sibs]
    try:
        i = norm.index(os.path.normcase(book_path))
    except ValueError:
        return None
    j = i + step
    while 0 <= j < len(sibs):
        cand = sibs[j]
        if os.path.isfile(cand) or folder_has_images(cand):
            return cand
        j += step
    return None


def book_display(path: str) -> str:
    return Path(path).name
