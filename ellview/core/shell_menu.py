"""Windows 탐색기 우클릭 메뉴 "Ellview로 열기" 등록/해제.

관리자 권한이 필요 없도록 현재 사용자 영역(HKEY_CURRENT_USER\\Software\\Classes)에만 씁니다.
- 폴더:           Directory\\shell\\Ellview
- 이미지/압축 파일: SystemFileAssociations\\<확장자>\\shell\\Ellview
등록 내용은 plan()이 만들고, 실제 레지스트리 쓰기는 Windows에서만 합니다(그 외 OS에선 plan만 테스트).
"""
from __future__ import annotations

import os
import sys

from ellview.config import app_base_dir
from ellview.core.formats import ARCHIVE_EXTS, IMAGE_EXTS

KEY_NAME = "Ellview"
MENU_TEXT = "Ellview로 열기"
_SKIP_EXTS = {".gz", ".bz2", ".xz"}  # 단독 압축은 tar가 아닐 수 있어 제외


def supported() -> bool:
    return sys.platform == "win32"


def target_exts() -> list[str]:
    return sorted((IMAGE_EXTS | set(ARCHIVE_EXTS)) - _SKIP_EXTS)


def launch_command() -> tuple[str, str]:
    """(명령줄, 아이콘 경로). exe로 실행 중이면 exe, 개발 모드면 pythonw + run.py."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return f'"{exe}" "%1"', exe
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
    if os.path.exists(pyw):
        py = pyw
    run = str(app_base_dir() / "run.py")
    icon = str(app_base_dir() / "assets" / "ellview.ico")
    return f'"{py}" "{run}" "%1"', icon


def key_paths() -> list[str]:
    paths = [rf"Software\Classes\Directory\shell\{KEY_NAME}"]
    paths += [rf"Software\Classes\SystemFileAssociations\{e}\shell\{KEY_NAME}" for e in target_exts()]
    return paths


def plan() -> list[tuple[str, dict, str]]:
    """[(메뉴 키 경로, 메뉴 키 값들, command 기본값)]"""
    cmd, icon = launch_command()
    values = {"": MENU_TEXT, "MUIVerb": MENU_TEXT, "Icon": icon}
    return [(k, values, cmd) for k in key_paths()]


def register() -> int:
    import winreg
    n = 0
    for key, values, cmd in plan():
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as k:
            for name, val in values.items():
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key + r"\command", 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        n += 1
    return n


def unregister() -> int:
    import winreg
    n = 0
    for key in key_paths():
        for sub in (key + r"\command", key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                if sub == key:
                    n += 1
            except FileNotFoundError:
                pass
    return n


def registered_command() -> str | None:
    """폴더 메뉴에 등록된 명령줄 (없으면 None)."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_paths()[0] + r"\command") as k:
            return winreg.QueryValueEx(k, "")[0]
    except OSError:
        return None


def ensure_current() -> bool:
    """exe를 다른 곳으로 옮겼으면 메뉴의 실행 경로를 지금 위치로 고칩니다. 바꿨으면 True."""
    if not supported():
        return False
    cur = registered_command()
    want = launch_command()[0]
    if cur != want:
        register()
        return True
    return False
