"""설정/데이터 저장 위치와 설정값 관리.

- exe(또는 run.py) 옆에 `portable.txt` 파일이 있으면 포터블 모드: 같은 폴더의 `data/`에 저장
- 아니면 Windows: %APPDATA%/Ellview, 그 외: ~/.config/Ellview
- 설정은 DEFAULTS와 병합되므로 새 버전에서 설정 항목이 추가돼도 기존 설정 파일이 그대로 동작합니다.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from ellview import APP_NAME

SETTINGS_SCHEMA = 2

DEFAULTS: dict[str, Any] = {
    "schema": SETTINGS_SCHEMA,
    # 보기
    "fit_mode": "window",          # window | width | height | original
    "upscale_small": False,        # 창보다 작은 이미지를 확대할지
    "two_page": False,
    "rtl": False,                  # 우→좌(만화) 읽기
    "cover_single": True,          # 두 페이지 보기에서 첫 페이지는 단독
    "wide_single": True,           # 가로로 긴 이미지는 단독 표시
    "theme": "dark",               # dark | light | system
    "background": "#1e1e1e",
    "smooth": True,
    "show_thumbnails": False,
    "show_statusbar": True,
    "info_overlay": False,
    # 동작
    "wheel_mode": "page",          # page: 휠=페이지 이동(넘칠 때는 스크롤 후 이동) | scroll: 휠=스크롤만
    "click_navigation": True,      # 화면 좌/우 클릭으로 페이지 이동
    # 휠·방향키·클릭으로 처음/끝을 넘어가려 할 때
    #   stop: 넘어가지 않고 알림만 (파일 이동은 [ ] / Ctrl+←→) | prompt: 안내 후 한 번 더 넘기면 이동 | auto: 바로 이동
    "boundary_action": "stop",
    "prev_book_start": "last",     # prompt/auto에서 첫 페이지를 넘어 이전 파일로 갈 때 시작 위치: last | first
    "resume_last_page": True,
    "preload_ahead": 3,
    "preload_behind": 1,
    "cache_mb": 512,
    "max_decode_megapixels": 120,  # 이보다 큰 이미지는 축소 디코딩
    "check_updates": True,
    "slideshow_interval": 3.0,     # 초
    "slideshow_end": "next_book",  # next_book | loop | stop
    "shell_menu": False,           # 탐색기 우클릭 메뉴 등록 여부
    # 책갈피 재탐색 시 뒤져볼 폴더들
    "library_roots": [],
    "relocate_max_depth": 6,
    # 단축키 (비어 있으면 기본값 사용)
    "shortcuts": {},
    # 창 상태
    "window_geometry": "",
    "window_state": "",
    "last_dir": "",
}


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    override = os.environ.get("ELLVIEW_DATA_DIR")
    if override:
        p = Path(override)
    elif (app_base_dir() / "portable.txt").exists():
        p = app_base_dir() / "data"
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    else:
        p = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = Path(tempfile.gettempdir()) / f"{APP_NAME}_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json(path: Path, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(default)


def save_json(path: Path, data: Any) -> None:
    """임시 파일에 쓰고 교체해서 저장 도중 꺼져도 파일이 깨지지 않게 합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "settings.json")
        raw = load_json(self.path, {})
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in DEFAULTS:
                    self.data[k] = v
            self._migrate(int(raw.get("schema", 1) or 1))
        self.data["schema"] = SETTINGS_SCHEMA

    def _migrate(self, old_schema: int):
        """이전 버전 설정 파일을 새 기본 동작에 맞게 옮깁니다."""
        if old_schema < 2 and self.data.get("boundary_action") == "prompt":
            # 0.2.1: 휠·방향키로는 파일을 넘기지 않고 알림만 (예전 기본값 prompt를 쓰던 경우만 변경)
            self.data["boundary_action"] = "stop"

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def save(self) -> None:
        save_json(self.path, self.data)
