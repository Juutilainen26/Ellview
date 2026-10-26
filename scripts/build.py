"""배포용 빌드: PyInstaller(onedir) → 7-Zip 동봉 → zip 묶기.

사용: python scripts/build.py
결과: dist/Ellview/Ellview.exe, dist/Ellview-<버전>-win64.zip (Windows 기준)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ellview import APP_NAME, __version__  # noqa: E402

VERSION_TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041204B0', [
      StringStruct('CompanyName', 'Ellview'),
      StringStruct('FileDescription', 'Ellview 이미지 뷰어'),
      StringStruct('FileVersion', '{s}'),
      StringStruct('InternalName', 'Ellview'),
      StringStruct('OriginalFilename', 'Ellview.exe'),
      StringStruct('ProductName', 'Ellview'),
      StringStruct('ProductVersion', '{s}')])]),
    VarFileInfo([VarStruct('Translation', [0x0412, 1200])])
  ]
)
"""


def write_version_file():
    nums = [int(x) for x in __version__.split(".")[:3]] + [0]
    nums = (nums + [0, 0, 0, 0])[:4]
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    with open(os.path.join(ROOT, "build", "version_info.txt"), "w", encoding="utf-8") as f:
        f.write(VERSION_TEMPLATE.format(v=", ".join(map(str, nums)), s=__version__))


def find_7zip_dir() -> str | None:
    if sys.platform != "win32":
        return None
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base and os.path.exists(os.path.join(base, "7-Zip", "7z.exe")):
            return os.path.join(base, "7-Zip")
    return None


def bundle_tools(app_dir: str):
    """RAR/특수 7z 해제를 위해 7-Zip(7z.exe + 7z.dll)을 tools/에 동봉."""
    tools = os.path.join(app_dir, "tools")
    os.makedirs(tools, exist_ok=True)
    src = find_7zip_dir()
    if not src:
        print("! 7-Zip을 찾지 못해 동봉하지 않습니다 (RAR은 Windows 내장 tar로 시도).")
        with open(os.path.join(tools, "README.txt"), "w", encoding="utf-8") as f:
            f.write("RAR 파일을 열려면 이 폴더에 7z.exe와 7z.dll(7-Zip 설치 폴더에 있음) 또는 UnRAR.exe를 넣어주세요.\n")
        return
    for name in ("7z.exe", "7z.dll", "License.txt"):
        p = os.path.join(src, name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(tools, "7-Zip-" + name if name == "License.txt" else name))
    print("7-Zip 동봉:", src)


def main():
    write_version_file()
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           os.path.join(ROOT, "ellview.spec")], cwd=ROOT)
    app_dir = os.path.join(ROOT, "dist", APP_NAME)
    bundle_tools(app_dir)
    for doc in ("README.md", "CHANGELOG.md", "LICENSE"):
        if os.path.exists(os.path.join(ROOT, doc)):
            shutil.copy2(os.path.join(ROOT, doc), app_dir)
    arch = "win64" if sys.platform == "win32" else f"{platform.system().lower()}-{platform.machine().lower()}"
    zip_path = os.path.join(ROOT, "dist", f"{APP_NAME}-{__version__}-{arch}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirs, files in os.walk(app_dir):
            for fn in files:
                full = os.path.join(dirpath, fn)
                z.write(full, os.path.join(APP_NAME, os.path.relpath(full, app_dir)))
    print("완료:", zip_path)


if __name__ == "__main__":
    main()
