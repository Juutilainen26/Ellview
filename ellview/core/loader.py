"""이미지 디코딩, 메모리 캐시, 백그라운드 미리 읽기."""
from __future__ import annotations

import io
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader

from ellview.core.formats import ANIM_EXTS, ext_of

QImageReader.setAllocationLimit(4096)  # MB. 기본 256MB 제한 때문에 큰 사진이 안 열리는 것 방지

_pil_ready = False

# Qt보다 Pillow가 잘 여는 형식
PILLOW_FIRST = {".avif", ".heic", ".heif", ".jxl", ".psd", ".apng", ".dds", ".qoi", ".pcx"}
# Qt의 TIFF 플러그인은 Pillow의 libtiff와 한 프로세스에서 충돌(크래시)할 수 있어 Pillow만 사용
PILLOW_ONLY = {".tif", ".tiff"}


def _init_pillow():
    global _pil_ready
    if _pil_ready:
        return
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    try:
        import pillow_jxl  # noqa: F401  (설치돼 있으면 JPEG XL 지원)
    except Exception:
        pass
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    _pil_ready = True


@dataclass
class Decoded:
    image: QImage
    orig_size: QSize
    fmt: str
    byte_size: int
    animated: bool = False
    data: bytes | None = None       # 애니메이션 재생용 원본 바이트
    downscaled: bool = False
    error: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def mem(self) -> int:
        n = self.image.sizeInBytes() if not self.image.isNull() else 0
        return n + (len(self.data) if self.data else 0)


def _is_animated(data: bytes, name: str) -> bool:
    if ext_of(name) not in ANIM_EXTS:
        return False
    _init_pillow()
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            # n_frames는 GIF 전체를 훑어야 해서 큰 파일에서 느림 → is_animated(2번째 프레임 존재 여부)만 확인
            return bool(getattr(im, "is_animated", False))
    except Exception:
        return False


def pil_to_qimage(im) -> QImage:
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if ("A" in im.mode or "transparency" in im.info) else "RGB")
    if im.mode == "RGBA":
        fmt = QImage.Format_RGBA8888
        stride = im.width * 4
    else:
        fmt = QImage.Format_RGB888
        stride = im.width * 3
    raw = im.tobytes()
    return QImage(raw, im.width, im.height, stride, fmt).copy()


def _decode_with_qt(data: bytes, max_pixels: int, target: QSize | None):
    ba = QByteArray(data)
    buf = QBuffer(ba)
    buf.open(QIODevice.ReadOnly)
    reader = QImageReader(buf)
    reader.setAutoTransform(True)
    fmt = bytes(reader.format()).decode(errors="ignore")
    size = reader.size()
    downscaled = False
    if size.isValid():
        if target is not None:
            s = size.scaled(target, Qt.KeepAspectRatio)
            if s.width() < size.width():
                reader.setScaledSize(s)
                downscaled = True
        elif size.width() * size.height() > max_pixels:
            f = (max_pixels / (size.width() * size.height())) ** 0.5
            reader.setScaledSize(QSize(max(1, int(size.width() * f)), max(1, int(size.height() * f))))
            downscaled = True
    img = reader.read()
    buf.close()
    if img.isNull():
        return None
    if not size.isValid():
        size = img.size()
    return img, size, fmt, downscaled


def _decode_with_pillow(data: bytes, max_pixels: int, target: QSize | None):
    _init_pillow()
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(data))
    fmt = (im.format or "").lower()
    orig = QSize(*im.size)
    downscaled = False
    w, h = im.size
    if target is not None:
        tw, th = target.width(), target.height()
    elif w * h > max_pixels:
        f = (max_pixels / (w * h)) ** 0.5
        tw, th = int(w * f), int(h * f)
    else:
        tw = th = 0
    if tw and (tw < w or th < h):
        try:
            im.draft("RGB", (tw, th))  # JPEG은 디코딩 단계에서 축소 → 빠르고 메모리 절약
        except Exception:
            pass
        im.thumbnail((tw, th))
        downscaled = True
    im = ImageOps.exif_transpose(im)
    if orig.width() != im.width and not downscaled:
        orig = QSize(im.width, im.height)
    return pil_to_qimage(im), orig, fmt, downscaled


def decode(data: bytes, name: str, max_megapixels: float = 120, target: QSize | None = None,
           detect_animation: bool = True) -> Decoded:
    """바이트를 QImage로. Qt가 못 여는 형식(AVIF/HEIC/PSD 등)은 Pillow로 시도합니다.
    target을 주면 그 크기 안으로 축소 디코딩(썸네일용)."""
    max_pixels = int(max_megapixels * 1_000_000)
    res = None
    err = None
    ext = ext_of(name)
    if ext in PILLOW_ONLY:
        order = (_decode_with_pillow,)
    elif ext in PILLOW_FIRST:
        order = (_decode_with_pillow, _decode_with_qt)
    else:
        order = (_decode_with_qt, _decode_with_pillow)
    for fn in order:
        try:
            res = fn(data, max_pixels, target)
        except Exception as e:  # 손상 파일 등
            err = f"{type(e).__name__}: {e}"
            res = None
        if res is not None:
            break
    if res is None:
        return Decoded(QImage(), QSize(), "", len(data), error=err or "이미지를 열 수 없습니다")
    img, orig, fmt, down = res
    animated = detect_animation and target is None and _is_animated(data, name)
    return Decoded(img, orig, fmt or ext.lstrip("."), len(data), animated=animated,
                   data=data if animated else None, downscaled=down)


# ------------------------------------------------------------------ 캐시
class ImageCache:
    def __init__(self, budget_mb: int = 512):
        self.budget = budget_mb * 1024 * 1024
        self._d: OrderedDict = OrderedDict()
        self._used = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            v = self._d.get(key)
            if v is not None:
                self._d.move_to_end(key)
            return v

    def put(self, key, value: Decoded, protect: set | None = None):
        with self._lock:
            old = self._d.pop(key, None)
            if old is not None:
                self._used -= old.mem
            self._d[key] = value
            self._used += value.mem
            protect = protect or set()
            for k in list(self._d.keys()):
                if self._used <= self.budget or len(self._d) <= 1:
                    break
                if k == key or k in protect:
                    continue
                v = self._d.pop(k)
                self._used -= v.mem

    def clear(self):
        with self._lock:
            self._d.clear()
            self._used = 0

    def drop_book(self, book_id: str):
        with self._lock:
            for k in [k for k in self._d if k[0] == book_id]:
                self._used -= self._d.pop(k).mem

    @property
    def used(self) -> int:
        return self._used


class _Signals(QObject):
    done = Signal(object, object)  # key, Decoded


class _DecodeTask(QRunnable):
    def __init__(self, book, index, max_mp, signals):
        super().__init__()
        self.book, self.index, self.max_mp, self.signals = book, index, max_mp, signals
        self.setAutoDelete(True)

    def run(self):
        key = (self.book.path, self.index)
        try:
            data = self.book.read(self.index)
            dec = decode(data, self.book.pages[self.index].name, self.max_mp)
        except Exception as e:
            dec = Decoded(QImage(), QSize(), "", 0, error=f"{type(e).__name__}: {e}")
        try:
            self.signals.done.emit(key, dec)
        except RuntimeError:
            pass


class PageLoader(QObject):
    """현재 책의 페이지를 캐시에서 주거나, 백그라운드에서 미리 읽어 둡니다."""
    loaded = Signal(object, object)  # key, Decoded

    def __init__(self, cache: ImageCache, parent=None):
        super().__init__(parent)
        self.cache = cache
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self._sig = _Signals()
        self._sig.done.connect(self._on_done)
        self._pending: set = set()
        self.book = None
        self.max_mp = 120

    def set_book(self, book):
        self.pool.clear()
        self._pending.clear()
        self.book = book

    def get_sync(self, index: int) -> Decoded:
        key = (self.book.path, index)
        d = self.cache.get(key)
        if d is not None:
            return d
        try:
            data = self.book.read(index)
            d = decode(data, self.book.pages[index].name, self.max_mp)
        except Exception as e:
            d = Decoded(QImage(), QSize(), "", 0, error=f"{type(e).__name__}: {e}")
        if d.error is None:
            self.cache.put(key, d)
        return d

    def cached(self, index: int):
        if self.book is None:
            return None
        return self.cache.get((self.book.path, index))

    def prefetch(self, indices):
        if self.book is None:
            return
        for i in indices:
            if not (0 <= i < len(self.book)):
                continue
            key = (self.book.path, i)
            if key in self._pending or self.cache.get(key) is not None:
                continue
            self._pending.add(key)
            self.pool.start(_DecodeTask(self.book, i, self.max_mp, self._sig))

    def _on_done(self, key, dec):
        self._pending.discard(key)
        if self.book is None or key[0] != self.book.path:
            return
        if dec.error is None:
            self.cache.put(key, dec)
        self.loaded.emit(key, dec)

    def wait(self):
        self.pool.waitForDone()
