"""최근 연 파일 목록과 책별 마지막 읽은 위치(이어보기)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from ellview.config import data_dir, load_json, save_json

MAX_RECENT = 20
MAX_POSITIONS = 3000


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "history.json")
        d = load_json(self.path, {})
        self.recent_list: list[dict] = list(d.get("recent", [])) if isinstance(d, dict) else []
        self.positions: dict[str, dict] = dict(d.get("positions", {})) if isinstance(d, dict) else {}
        self._dirty = False

    # --- 이어보기
    def get_position(self, path: str) -> dict | None:
        return self.positions.get(norm(path))

    def set_position(self, path: str, index: int, name: str, count: int):
        self.positions[norm(path)] = {"index": index, "name": name, "count": count, "time": time.time()}
        if len(self.positions) > MAX_POSITIONS:
            oldest = sorted(self.positions.items(), key=lambda kv: kv[1].get("time", 0))
            for k, _ in oldest[: len(self.positions) - MAX_POSITIONS]:
                del self.positions[k]
        self._dirty = True

    # --- 최근 파일
    def add_recent(self, path: str):
        n = norm(path)
        self.recent_list = [r for r in self.recent_list if norm(r["path"]) != n]
        self.recent_list.insert(0, {"path": os.path.abspath(path), "time": time.time()})
        del self.recent_list[MAX_RECENT:]
        self._dirty = True

    def recent(self) -> list[str]:
        return [r["path"] for r in self.recent_list]

    def clear_recent(self):
        self.recent_list = []
        self._dirty = True

    def save(self, force: bool = False):
        if self._dirty or force:
            save_json(self.path, {"recent": self.recent_list, "positions": self.positions})
            self._dirty = False
