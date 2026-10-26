"""압축파일 백엔드.

새 압축 형식을 추가하려면 ArchiveBackend를 상속한 클래스를 만들고
`register_backend("이름", 클래스)`로 등록한 뒤 formats.ARCHIVE_EXTS에 확장자를 추가하면 됩니다.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tarfile
import threading
import zipfile
from pathlib import Path

from ellview.config import app_base_dir, cache_dir
from ellview.core.formats import archive_backend_for, is_image_name


def find_7z() -> str | None:
    """번들(tools/7z.exe) → PATH(7z/7zz/7za) → 기본 설치 위치 순으로 7-Zip 실행 파일을 찾습니다."""
    for cand in ("7z.exe", "7z", "7zz"):
        p = app_base_dir() / "tools" / cand
        if p.exists():
            return str(p)
    for cand in ("7z", "7zz", "7za"):
        p = shutil.which(cand)
        if p:
            return p
    if sys.platform == "win32":
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base and os.path.exists(os.path.join(base, "7-Zip", "7z.exe")):
                return os.path.join(base, "7-Zip", "7z.exe")
    return None


def _run_hidden(args, **kw):
    """Windows에서 콘솔 창이 깜빡이지 않게 실행."""
    import subprocess
    if sys.platform == "win32":
        kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(args, capture_output=True, **kw)


class ArchiveError(Exception):
    pass


class PasswordRequired(ArchiveError):
    pass


def _skip_entry(name: str) -> bool:
    n = name.replace("\\", "/")
    base = n.rsplit("/", 1)[-1]
    return n.startswith("__MACOSX/") or "/__MACOSX/" in n or base.startswith("._")


class ArchiveBackend:
    """압축파일 하나를 연 상태. names()는 이미지 항목 이름, read()는 해당 바이트."""

    def __init__(self, path: str, password: str | None = None):
        self.path = path
        self.password = password
        self._lock = threading.Lock()

    def names(self) -> list[str]:
        raise NotImplementedError

    def read(self, name: str) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- ZIP
def _fix_zip_name(zi: zipfile.ZipInfo) -> str:
    """UTF-8 플래그가 없는 zip(한국 윈도우에서 만든 것 등)의 파일명을 CP949로 복원."""
    name = zi.filename
    if zi.flag_bits & 0x800:
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in ("utf-8", "cp949", "shift_jis"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return name


class ZipBackend(ArchiveBackend):
    def __init__(self, path, password=None):
        super().__init__(path, password)
        try:
            self.zf = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as e:
            raise ArchiveError(str(e)) from e
        self._map: dict[str, zipfile.ZipInfo] = {}
        for zi in self.zf.infolist():
            if zi.is_dir():
                continue
            name = _fix_zip_name(zi)
            if _skip_entry(name) or not is_image_name(name):
                continue
            self._map[name] = zi
        self._encrypted = any(zi.flag_bits & 0x1 for zi in self._map.values())

    def names(self):
        return list(self._map)

    def read(self, name):
        zi = self._map[name]
        with self._lock:
            try:
                pwd = self.password.encode("utf-8") if self.password else None
                return self.zf.read(zi, pwd=pwd)
            except RuntimeError as e:
                if "password" in str(e).lower() or "encrypted" in str(e).lower():
                    raise PasswordRequired(str(e)) from e
                raise ArchiveError(str(e)) from e
            except (zipfile.BadZipFile, OSError) as e:
                raise ArchiveError(str(e)) from e

    def close(self):
        self.zf.close()


# ---------------------------------------------------------------- TAR
class TarBackend(ArchiveBackend):
    def __init__(self, path, password=None):
        super().__init__(path, password)
        try:
            self.tf = tarfile.open(path, "r:*")
        except (tarfile.TarError, OSError) as e:
            raise ArchiveError(str(e)) from e
        self._map = {}
        for m in self.tf.getmembers():
            if m.isfile() and not _skip_entry(m.name) and is_image_name(m.name):
                self._map[m.name] = m

    def names(self):
        return list(self._map)

    def read(self, name):
        with self._lock:
            f = self.tf.extractfile(self._map[name])
            if f is None:
                raise ArchiveError(name)
            return f.read()

    def close(self):
        self.tf.close()


# ---------------------------------------------------------------- 7Z
class SevenZipBackend(ArchiveBackend):
    """7z는 대부분 '솔리드' 압축이라 항목별 임의 접근이 느립니다.
    처음 읽을 때 임시 캐시 폴더에 한 번에 풀어두고 그 뒤로는 파일에서 읽습니다."""

    def __init__(self, path, password=None):
        super().__init__(path, password)
        import py7zr
        self._py7zr = py7zr
        try:
            with py7zr.SevenZipFile(path, "r", password=password) as z:
                if z.needs_password() and not password:
                    raise PasswordRequired(path)
                all_names = z.getnames()
                infos = {i.filename: i for i in z.list()}
        except PasswordRequired:
            raise
        except Exception as e:  # py7zr는 다양한 예외를 던짐
            if "password" in str(e).lower():
                raise PasswordRequired(str(e)) from e
            raise ArchiveError(str(e)) from e
        self._names = [n for n in all_names
                       if not (infos.get(n) and infos[n].is_directory)
                       and not _skip_entry(n) and is_image_name(n)]
        st = os.stat(path)
        key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
        self._dir = cache_dir() / f"7z_{key}"
        self._extracted = (self._dir / ".done").exists()

    def names(self):
        return list(self._names)

    def _ensure_extracted(self):
        if self._extracted:
            return
        tmp = self._dir.with_name(self._dir.name + "_part")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            with self._py7zr.SevenZipFile(self.path, "r", password=self.password) as z:
                z.extract(path=tmp, targets=self._names)
        except Exception as e:
            # py7zr가 지원하지 않는 필터(BCJ2 등)면 7-Zip 실행 파일로 재시도
            exe = find_7z()
            ok = False
            if exe and "password" not in str(e).lower():
                r = _run_hidden([exe, "x", "-y", f"-o{tmp}", f"-p{self.password or ''}", self.path])
                ok = r.returncode == 0
            if not ok:
                shutil.rmtree(tmp, ignore_errors=True)
                if "password" in str(e).lower():
                    raise PasswordRequired(str(e)) from e
                raise ArchiveError(str(e)) from e
        shutil.rmtree(self._dir, ignore_errors=True)
        os.replace(tmp, self._dir)
        (self._dir / ".done").write_text("ok")
        self._extracted = True

    def read(self, name):
        with self._lock:
            self._ensure_extracted()
            target = (self._dir / name).resolve()
            if self._dir.resolve() not in target.parents:
                raise ArchiveError("잘못된 경로: " + name)
            return target.read_bytes()


# ---------------------------------------------------------------- RAR
_rar_configured = False


def _configure_rar():
    """unrar 실행 도구를 찾아 rarfile에 알려줍니다.
    우선순위: Ellview/tools/UnRAR.exe → PATH의 unrar/unar/7z → Windows 내장 tar.exe(bsdtar)."""
    global _rar_configured
    if _rar_configured:
        return
    import rarfile
    tools = app_base_dir() / "tools"
    for cand in ("UnRAR.exe", "unrar.exe", "unrar"):
        p = tools / cand
        if p.exists():
            rarfile.UNRAR_TOOL = str(p)
            break
    seven = find_7z()
    if seven:
        rarfile.SEVENZIP_TOOL = seven
    if sys.platform == "win32":
        win_tar = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
        if win_tar.exists():
            rarfile.BSDTAR_TOOL = str(win_tar)
    try:
        rarfile.tool_setup(force=True)
    except rarfile.RarCannotExec:
        pass
    _rar_configured = True


class RarBackend(ArchiveBackend):
    def __init__(self, path, password=None):
        super().__init__(path, password)
        import rarfile
        _configure_rar()
        self._rarfile = rarfile
        try:
            self.rf = rarfile.RarFile(path)
            if password:
                self.rf.setpassword(password)
            elif self.rf.needs_password():
                raise PasswordRequired(path)
        except PasswordRequired:
            raise
        except (rarfile.Error, OSError) as e:
            raise ArchiveError(str(e)) from e
        self._names = [i.filename for i in self.rf.infolist()
                       if not i.is_dir() and not _skip_entry(i.filename) and is_image_name(i.filename)]

    def names(self):
        return list(self._names)

    def read(self, name):
        with self._lock:
            try:
                return self.rf.read(name)
            except self._rarfile.RarCannotExec as e:
                raise ArchiveError("RAR 압축 해제 도구를 찾지 못했습니다.\n"
                                   "Ellview 폴더의 tools 안에 7z.exe+7z.dll 또는 UnRAR.exe를 넣어주세요.") from e
            except self._rarfile.PasswordRequired as e:
                raise PasswordRequired(str(e)) from e
            except (self._rarfile.Error, OSError) as e:
                raise ArchiveError(str(e)) from e

    def close(self):
        self.rf.close()


_BACKENDS: dict[str, type[ArchiveBackend]] = {}


def register_backend(name: str, cls: type[ArchiveBackend]) -> None:
    _BACKENDS[name] = cls


register_backend("zip", ZipBackend)
register_backend("tar", TarBackend)
register_backend("7z", SevenZipBackend)
register_backend("rar", RarBackend)


def open_archive(path: str, password: str | None = None) -> ArchiveBackend:
    kind = archive_backend_for(path)
    if kind is None:
        raise ArchiveError("지원하지 않는 압축 형식: " + path)
    # 확장자가 틀린 경우(예: .cbr인데 실제론 zip) 내용으로 재판별
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except OSError as e:
        raise ArchiveError(str(e)) from e
    if head.startswith(b"PK"):
        kind = "zip"
    elif head.startswith(b"Rar!"):
        kind = "rar"
    elif head.startswith(b"7z\xbc\xaf\x27\x1c"):
        kind = "7z"
    return _BACKENDS[kind](path, password)


def cleanup_cache(max_age_days: float = 3.0) -> None:
    """오래된 7z 임시 캐시 정리."""
    import time
    now = time.time()
    for p in cache_dir().glob("7z_*"):
        try:
            if now - p.stat().st_mtime > max_age_days * 86400:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass
