"""움직이는 이미지(GIF/WebP/APNG/AVIF) 재생기.

GIF·WebP는 QMovie로 스트리밍 재생(프레임을 전부 메모리에 올리지 않아 큰 GIF도 가볍게),
그 외(APNG 등)는 Pillow로 프레임을 순서대로 디코딩합니다.
"""
from __future__ import annotations

import io

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, Signal
from PySide6.QtGui import QImage, QMovie

from ellview.core.loader import _init_pillow, pil_to_qimage


class AnimPlayer(QObject):
    frameChanged = Signal()

    def __init__(self, data: bytes, fmt: str, first: QImage, parent=None):
        super().__init__(parent)
        self._image = first
        self._movie = None
        self._timer = None
        self._paused = False
        fmt = (fmt or "").lower()
        qt_fmts = {bytes(f).decode() for f in QMovie.supportedFormats()}
        if fmt in qt_fmts:
            self._ba = QByteArray(data)
            self._buf = QBuffer(self._ba)
            self._buf.open(QIODevice.ReadOnly)
            m = QMovie(self._buf, QByteArray(fmt.encode()))
            m.setCacheMode(QMovie.CacheNone)
            if m.isValid():
                self._movie = m
                m.frameChanged.connect(self._on_movie_frame)
        if self._movie is None:
            self._init_pil(data)

    # --- Pillow 재생
    def _init_pil(self, data: bytes):
        _init_pillow()
        from PIL import Image
        self._pil = Image.open(io.BytesIO(data))
        self._frame = 0
        self._n = getattr(self._pil, "n_frames", 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next_pil)

    def _next_pil(self):
        if self._paused:
            return
        self._frame = (self._frame + 1) % self._n
        try:
            self._pil.seek(self._frame)
            self._image = pil_to_qimage(self._pil.convert("RGBA"))
        except Exception:
            return
        self.frameChanged.emit()
        self._schedule()

    def _schedule(self):
        d = self._pil.info.get("duration", 100) or 100
        self._timer.start(max(20, int(d)))

    def _on_movie_frame(self, _n):
        self._image = self._movie.currentImage()
        self.frameChanged.emit()

    # --- 공개 API
    def start(self):
        self._paused = False
        if self._movie is not None:
            self._movie.start()
        elif self._timer is not None and self._n > 1:
            self._pil.seek(0)
            self._schedule()

    def stop(self):
        if self._movie is not None:
            self._movie.stop()
        if self._timer is not None:
            self._timer.stop()

    def toggle_pause(self) -> bool:
        self._paused = not self._paused
        if self._movie is not None:
            self._movie.setPaused(self._paused)
        elif self._timer is not None:
            if self._paused:
                self._timer.stop()
            else:
                self._schedule()
        return self._paused

    @property
    def paused(self) -> bool:
        return self._paused

    def frame_count(self) -> int:
        if self._movie is not None:
            return self._movie.frameCount()
        return getattr(self, "_n", 1)

    def current_image(self) -> QImage:
        return self._image
