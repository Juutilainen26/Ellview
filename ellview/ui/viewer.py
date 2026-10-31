"""이미지를 그리는 중앙 위젯: 맞춤 모드, 확대/축소, 끌어서 이동, 두 페이지 배치, 애니메이션."""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QLabel, QWidget

from ellview.core.loader import Decoded
from ellview.ui.animation import AnimPlayer

FIT_MODES = ("window", "width", "height", "original")
SIDE_ZONE = 0.2   # 가로: 화면을 5등분했을 때 맨 왼쪽/오른쪽 한 칸
BAND_ZONE = 0.3   # 세로: 그 칸 중 가운데 30%만 클릭 넘김 영역 (위·아래 35%씩은 제외)


class PageImage:
    def __init__(self, dec: Decoded, name: str = ""):
        self.dec = dec
        self.name = name
        self.player: AnimPlayer | None = None
        if dec.animated and dec.data:
            try:
                self.player = AnimPlayer(dec.data, dec.fmt, dec.image)
            except Exception:
                self.player = None
        self._scaled: QPixmap | None = None
        self._scaled_key = None
        self.rotation = 0      # 0/90/180/270 (시계 방향)
        self.flip = False      # 좌우 반전
        self._oriented: QImage | None = None
        self._oriented_key = None

    def set_orientation(self, rotation: int, flip: bool):
        if (rotation, flip) != (self.rotation, self.flip):
            self.rotation, self.flip = rotation % 360, flip
            self._scaled_key = None

    @property
    def raw_size(self) -> QSize:
        if self.dec.orig_size.isValid() and not self.dec.orig_size.isEmpty():
            return self.dec.orig_size
        if not self.dec.image.isNull():
            return self.dec.image.size()
        return QSize(800, 1100)

    @property
    def size(self) -> QSize:
        sz = self.raw_size
        return sz.transposed() if self.rotation in (90, 270) else sz

    def raw_image(self) -> QImage:
        if self.player is not None:
            return self.player.current_image()
        return self.dec.image

    def image(self) -> QImage:
        """회전/반전이 적용된 이미지."""
        img = self.raw_image()
        if not self.rotation and not self.flip or img.isNull():
            return img
        if self.player is None and self._oriented_key == (self.rotation, self.flip):
            return self._oriented
        out = img
        if self.flip:
            # Qt 6.9+는 flipped, 그 이전은 mirrored
            out = out.flipped(Qt.Horizontal) if hasattr(out, "flipped") else out.mirrored(True, False)
        if self.rotation:
            out = out.transformed(QTransform().rotate(self.rotation))
        if self.player is None:
            self._oriented, self._oriented_key = out, (self.rotation, self.flip)
        return out

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.player.deleteLater()
            self.player = None


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel{background:rgba(20,20,20,215);color:#f2f2f2;border:1px solid rgba(255,255,255,40);"
            "border-radius:10px;padding:10px 18px;font-size:14px;}")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_text(self, text: str, ms: int = 1800):
        self.setText(text)
        pw = self.parentWidget().width()
        fm = self.fontMetrics()
        longest = max((fm.horizontalAdvance(line) for line in text.split("\n")), default=100)
        w = min(max(200, int(pw * 0.9)), longest + 48)
        self.setFixedWidth(w)
        self.setFixedHeight(self.heightForWidth(w) if self.heightForWidth(w) > 0 else self.sizeHint().height())
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def reposition(self):
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 40)


class Viewer(QWidget):
    nextRequested = Signal()
    prevRequested = Signal()
    doubleClicked = Signal()
    zoomChanged = Signal(float)
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAcceptDrops(True)
        self.setMinimumSize(200, 150)
        self.pages: list[PageImage] = []
        self.fit_mode = "window"
        self.zoom = 1.0
        self.rtl = False
        self.upscale_small = False
        self.smooth = True
        self.wheel_mode = "page"
        self.click_navigation = True
        self.bg = QColor("#1e1e1e")
        self.info_text = ""
        self.empty_text = "파일을 끌어다 놓거나 Ctrl+O로 열어주세요"
        self.sx = 0.0
        self.sy = 0.0
        self._drag_pos = None
        self._press_pos = None
        self._moved = False
        self._wheel_acc = 0
        self._edge_time = 0.0
        self._last_scroll_time = 0.0
        self.toast = Toast(self)
        self._pending_click = None
        self.rotation = 0
        self.flip = False
        self._hover_zone = None  # 'left' | 'right' | None
        self.setMouseTracking(True)

    # ------------------------------------------------------------ 페이지
    def set_pages(self, pages: list[PageImage], anchor: str = "start"):
        for p in self.pages:
            if p not in pages:
                p.stop()
        self.pages = pages
        for p in pages:
            p.set_orientation(self.rotation, self.flip)
            if p.player is not None:
                p.player.frameChanged.connect(self.update)
                p.player.start()
        self._reset_scroll(anchor)
        self.update()

    def clear(self):
        self.set_pages([])

    def set_orientation(self, rotation: int, flip: bool):
        """회전/반전은 뷰어에 남아 있어서 페이지·파일을 넘겨도 유지됩니다 (설정 파일에는 저장 안 함)."""
        self.rotation, self.flip = rotation % 360, flip
        for p in self.pages:
            p.set_orientation(self.rotation, self.flip)
        self._reset_scroll("start")
        self.update()

    def _reset_scroll(self, anchor):
        dw, dh = self.display_size()
        maxx = max(0.0, dw - self.width())
        maxy = max(0.0, dh - self.height())
        if anchor == "end":
            self.sy = maxy
            self.sx = 0.0 if self.rtl else maxx
        else:
            self.sy = 0.0
            self.sx = maxx if self.rtl else 0.0

    def toggle_animation(self) -> bool | None:
        res = None
        for p in self.pages:
            if p.player is not None:
                res = p.player.toggle_pause()
        return res

    # ------------------------------------------------------------ 배치 계산
    def _content(self):
        if not self.pages:
            return 0.0, 0.0, []
        h = max(p.size.height() for p in self.pages) or 1
        widths = [p.size.width() * h / max(1, p.size.height()) for p in self.pages]
        return float(sum(widths)), float(h), widths

    def scale_for(self, mode: str) -> float:
        cw, ch, _ = self._content()
        if cw <= 0 or ch <= 0:
            return 1.0
        vw, vh = max(1, self.width()), max(1, self.height())
        if mode == "window":
            s = min(vw / cw, vh / ch)
        elif mode == "width":
            s = vw / cw
        elif mode == "height":
            s = vh / ch
        elif mode == "original":
            s = 1.0
        else:
            s = self.zoom
        if mode in ("window", "width", "height") and not self.upscale_small:
            s = min(s, 1.0)
        return s

    def current_scale(self) -> float:
        return self.scale_for(self.fit_mode)

    def display_size(self):
        cw, ch, _ = self._content()
        s = self.current_scale()
        return cw * s, ch * s

    def _clamp(self):
        dw, dh = self.display_size()
        self.sx = min(max(0.0, self.sx), max(0.0, dw - self.width()))
        self.sy = min(max(0.0, self.sy), max(0.0, dh - self.height()))

    def _origin(self):
        self._clamp()
        dw, dh = self.display_size()
        x0 = (self.width() - dw) / 2 if dw <= self.width() else -self.sx
        y0 = (self.height() - dh) / 2 if dh <= self.height() else -self.sy
        return x0, y0

    def page_rects(self):
        cw, ch, widths = self._content()
        s = self.current_scale()
        x0, y0 = self._origin()
        order = list(range(len(self.pages)))
        if self.rtl:
            order.reverse()
        out = []
        x = x0
        for i in order:
            w = widths[i] * s
            out.append((self.pages[i], QRectF(x, y0, w, ch * s)))
            x += w
        return out

    def overflow(self):
        dw, dh = self.display_size()
        return dw > self.width() + 0.5, dh > self.height() + 0.5

    # ------------------------------------------------------------ 스크롤/확대
    def scroll_by(self, dx: float, dy: float) -> bool:
        ox, oy = self.sx, self.sy
        self.sx += dx
        self.sy += dy
        self._clamp()
        moved = abs(self.sx - ox) > 0.1 or abs(self.sy - oy) > 0.1
        if moved:
            self.update()
        return moved

    def scroll_step(self, direction: int) -> bool:
        """방향키 위/아래: 넘치면 스크롤, 더 갈 곳이 없으면 False."""
        return self.scroll_by(0, direction * max(60, self.height() * 0.25))

    def set_fit_mode(self, mode: str):
        self.fit_mode = mode
        self._reset_scroll("start")
        self.update()
        self.zoomChanged.emit(self.current_scale())

    def zoom_by(self, factor: float, anchor: QPointF | None = None):
        if not self.pages:
            return
        s = self.current_scale()
        new = min(32.0, max(0.02, s * factor))
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        x0, y0 = self._origin()
        cx, cy = (anchor.x() - x0) / s, (anchor.y() - y0) / s
        self.fit_mode = "custom"
        self.zoom = new
        dw, dh = self.display_size()
        self.sx = cx * new - anchor.x() if dw > self.width() else 0.0
        self.sy = cy * new - anchor.y() if dh > self.height() else 0.0
        self._clamp()
        self.update()
        self.zoomChanged.emit(new)

    def set_zoom(self, value: float):
        self.fit_mode = "custom"
        self.zoom = value
        self._reset_scroll("start")
        self.update()
        self.zoomChanged.emit(value)

    # ------------------------------------------------------------ 그리기
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), self.bg)
        if not self.pages:
            p.setPen(QColor(150, 150, 150))
            f = QFont(self.font())
            f.setPointSize(12)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, self.empty_text)
            return
        if self.smooth:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        s = self.current_scale()
        for page, r in self.page_rects():
            if page.dec.error or page.image().isNull():
                p.setPen(QColor(220, 120, 120))
                p.drawRect(r.adjusted(4, 4, -4, -4))
                p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap,
                           f"이미지를 표시할 수 없습니다\n{page.name}\n{page.dec.error or ''}")
                continue
            img = page.image()
            if page.player is None and self.smooth and s < 0.999:
                key = (int(round(r.width())), int(round(r.height())))
                if page._scaled_key != key:
                    page._scaled = QPixmap.fromImage(
                        img.scaled(key[0], key[1], Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                    page._scaled_key = key
                p.drawPixmap(int(round(r.x())), int(round(r.y())), page._scaled)
            else:
                p.drawImage(r, img)
        if self._hover_zone and self._drag_pos is None:
            self._paint_arrow(p, self._hover_zone)
        if self.info_text:
            f = QFont(self.font())
            f.setPointSize(10)
            p.setFont(f)
            br = p.boundingRect(QRectF(12, 12, self.width() - 24, 400), Qt.TextWordWrap, self.info_text)
            p.fillRect(br.adjusted(-8, -6, 8, 6), QColor(0, 0, 0, 160))
            p.setPen(QColor(235, 235, 235))
            p.drawText(br, Qt.TextWordWrap, self.info_text)

    def _paint_arrow(self, p: QPainter, zone: str):
        w, h = self.width(), self.height()
        zw = w * SIDE_ZONE
        x0 = 0 if zone == "left" else w - zw
        bh = h * BAND_ZONE
        y0 = (h - bh) / 2
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(x0 + 4, y0, zw - 8, bh), 10, 10)
        cx = x0 + zw / 2
        cy = h / 2
        r = max(18.0, min(34.0, zw * 0.22, bh * 0.35))
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawEllipse(QPointF(cx, cy), r, r)
        pen = QPen(QColor(255, 255, 255, 230), max(3.0, r * 0.16), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        a = r * 0.38
        d = -1 if zone == "left" else 1
        path = QPainterPath(QPointF(cx - d * a * 0.5, cy - a))
        path.lineTo(QPointF(cx + d * a * 0.5, cy))
        path.lineTo(QPointF(cx - d * a * 0.5, cy + a))
        p.drawPath(path)

    def zone_at(self, x: float, y: float) -> str | None:
        """클릭 넘김 영역: 양 끝 20% 칸 중 세로 가운데 30%. 그 밖은 None(가운데 영역과 같은 취급)."""
        if not self.click_navigation or not self.pages:
            return None
        h = self.height()
        if not (h * (1 - BAND_ZONE) / 2 <= y <= h * (1 + BAND_ZONE) / 2):
            return None
        if x < self.width() * SIDE_ZONE:
            return "left"
        if x > self.width() * (1 - SIDE_ZONE):
            return "right"
        return None

    def _set_hover(self, zone):
        if zone != self._hover_zone:
            self._hover_zone = zone
            if zone:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.unsetCursor()
            self.update()

    def leaveEvent(self, e):
        self._set_hover(None)
        super().leaveEvent(e)

    def resizeEvent(self, e):
        self._clamp()
        self.toast.reposition()
        super().resizeEvent(e)

    # ------------------------------------------------------------ 마우스
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.position()
            self._drag_pos = e.position()
            self._moved = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not e.buttons():
            self._set_hover(self.zone_at(e.position().x(), e.position().y()))
            return
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            d = e.position() - self._drag_pos
            if (e.position() - self._press_pos).manhattanLength() > 6:
                self._moved = True
            if self._moved and any(self.overflow()):
                if self._hover_zone:
                    self._set_hover(None)
                self.setCursor(Qt.ClosedHandCursor)
                self.scroll_by(-d.x(), -d.y())
            self._drag_pos = e.position()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.unsetCursor()
            self._hover_zone = None
            if not self._moved and self._press_pos is not None and self.click_navigation:
                # 양옆 영역은 기다리지 않고 바로 넘김 (가운데 영역만 더블클릭=전체 화면에 사용)
                self._pending_click = self._press_pos
                self._do_click()
            self._drag_pos = None
            self._press_pos = None
            self._set_hover(self.zone_at(e.position().x(), e.position().y()))
        super().mouseReleaseEvent(e)

    def _do_click(self):
        pos = self._pending_click
        self._pending_click = None
        if pos is None:
            return
        zone = self.zone_at(pos.x(), pos.y())
        if zone is None:
            return
        go_next = (zone == "right") != self.rtl  # RTL이면 왼쪽 클릭이 다음
        (self.nextRequested if go_next else self.prevRequested).emit()

    def _in_side_zone(self, pos) -> bool:
        return self.zone_at(pos.x(), pos.y()) is not None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._in_side_zone(e.position()):
                # 양옆을 빠르게 두 번 누른 것 = 두 장 넘기기 (두 번째 넘김은 이어지는 release에서 처리)
                self._press_pos = e.position()
                self._drag_pos = e.position()
                self._moved = False
                return
            self.doubleClicked.emit()

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if dy == 0:
            return
        if e.modifiers() & Qt.ControlModifier:
            self.zoom_by(1.15 if dy > 0 else 1 / 1.15, e.position())
            return
        now = time.monotonic()
        _, ov_y = self.overflow()
        if self.wheel_mode == "scroll" or ov_y:
            if self.scroll_by(0, -dy * 1.2):
                self._last_scroll_time = now
                return
            if self.wheel_mode == "scroll":
                return
            # 스크롤 끝에 막 닿았을 때 바로 페이지가 넘어가지 않도록 잠깐 멈춤
            if now - self._last_scroll_time < 0.35:
                return
        self._wheel_acc += dy
        if abs(self._wheel_acc) >= 120:
            forward = self._wheel_acc < 0
            self._wheel_acc = 0
            (self.nextRequested if forward else self.prevRequested).emit()

    # ------------------------------------------------------------ 드래그 앤 드롭
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
