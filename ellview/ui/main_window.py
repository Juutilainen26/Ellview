from __future__ import annotations

import os
import subprocess
import sys
import time

from PySide6.QtCore import QByteArray, QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFileDialog, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QSlider,
)

from ellview import APP_NAME, GITHUB_REPO, __version__
from ellview.core import updater
from ellview.core.archives import ArchiveError, PasswordRequired
from ellview.core.bookmarks import Bookmark, BookmarkStore, relocate
from ellview.core.books import FolderBook, neighbor_book, open_path, sibling_books
from ellview.core.formats import ARCHIVE_EXTS, IMAGE_EXTS, is_archive_name, natural_key
from ellview.core.history import History
from ellview.core.loader import ImageCache, PageLoader
from ellview.core.spread import last_start, prev_start, spread_at
from ellview.ui.dialogs import BookmarksDialog, HtmlDialog, SettingsDialog, about_html, shortcut_help_html
from ellview.ui.shortcuts import ACTIONS, keys_for
from ellview.ui.thumbnails import ThumbnailList
from ellview.ui.viewer import PageImage, Viewer

BOUNDARY_TIMEOUT = 4.0

TOGGLE_ACTIONS = {
    "toggle_two_page": "two_page", "toggle_rtl": "rtl", "toggle_cover": "cover_single",
    "toggle_upscale": "upscale_small", "toggle_thumbnails": "show_thumbnails",
    "toggle_statusbar": "show_statusbar", "toggle_info": "info_overlay",
}
FIT_ACTIONS = {"fit_window": "window", "fit_width": "width", "fit_height": "height", "fit_original": "original"}


def human_size(n: int) -> str:
    if n < 0:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


class _UpdateSig(QObject):
    result = Signal(object, bool)


class _UpdateTask(QRunnable):
    def __init__(self, sig, manual):
        super().__init__()
        self.sig, self.manual = sig, manual

    def run(self):
        info = updater.fetch_latest(GITHUB_REPO)
        try:
            self.sig.result.emit(info, self.manual)
        except RuntimeError:
            pass


class MainWindow(QMainWindow):
    def __init__(self, settings, history: History | None = None, bookmarks: BookmarkStore | None = None):
        super().__init__()
        self.s = settings
        self.history = history or History()
        self.bookmarks = bookmarks or BookmarkStore()
        self.book = None
        self.index = 0
        self.spread: list[int] = []
        self._boundary = None  # (방향, 대상 경로, 시각)
        self._fullscreen_restore = None

        self.setWindowTitle(APP_NAME)
        self.resize(1100, 800)
        self.viewer = Viewer(self)
        self.setCentralWidget(self.viewer)
        self.viewer.nextRequested.connect(self.act_next_page)
        self.viewer.prevRequested.connect(self.act_prev_page)
        self.viewer.doubleClicked.connect(self.act_toggle_fullscreen)
        self.viewer.zoomChanged.connect(lambda _z: self._update_status())
        self.viewer.filesDropped.connect(lambda paths: self.open_any(paths[0]))
        self.viewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.viewer.customContextMenuRequested.connect(self._context_menu)

        self.cache = ImageCache(self.s["cache_mb"])
        self.loader = PageLoader(self.cache, self)

        # 썸네일 패널
        self.thumbs = ThumbnailList()
        self.thumbs.pageClicked.connect(lambda i: self.show_index(i))
        self.dock = QDockWidget("썸네일", self)
        self.dock.setObjectName("thumbnails")
        self.dock.setWidget(self.thumbs)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.dock.visibilityChanged.connect(self._dock_visibility)

        # 상태 표시줄
        self.status_label = QLabel("")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setFixedWidth(220)
        self.slider.setMinimum(1)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(lambda v: self.statusBar().showMessage(f"{v} / {self.slider.maximum()}", 800))
        self.slider.sliderReleased.connect(lambda: self.show_index(self.slider.value() - 1))
        self.update_label = QLabel("")
        self.update_label.setOpenExternalLinks(True)
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.update_label)
        self.statusBar().addPermanentWidget(self.slider)

        self._build_actions()
        self._build_menus()
        self.apply_settings()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1500)
        self._save_timer.timeout.connect(self.history.save)

        self._upd_sig = _UpdateSig()
        self._upd_sig.result.connect(self._on_update_result)
        self._restore_window()
        if self.s["check_updates"] and GITHUB_REPO:
            QTimer.singleShot(2500, lambda: QThreadPool.globalInstance().start(_UpdateTask(self._upd_sig, False)))

    # ================================================================ 액션/메뉴
    def _build_actions(self):
        self.actions: dict[str, QAction] = {}
        overrides = self.s["shortcuts"] or {}
        for aid, label, _defaults, _cat in ACTIONS:
            a = QAction(label, self)
            a.setShortcuts([QKeySequence(k) for k in keys_for(aid, overrides)])
            a.setShortcutContext(Qt.WindowShortcut)
            if aid in TOGGLE_ACTIONS or aid in FIT_ACTIONS or aid == "toggle_fullscreen":
                a.setCheckable(True)
            handler = getattr(self, "act_" + aid, None)
            if handler is not None:
                a.triggered.connect(lambda _checked=False, h=handler: h())
            self.addAction(a)  # 메뉴를 숨긴 전체 화면에서도 단축키 동작
            self.actions[aid] = a
        self.fit_group = QActionGroup(self)
        for aid in FIT_ACTIONS:
            self.fit_group.addAction(self.actions[aid])

    def reload_shortcuts(self):
        overrides = self.s["shortcuts"] or {}
        for aid, a in self.actions.items():
            a.setShortcuts([QKeySequence(k) for k in keys_for(aid, overrides)])

    def _build_menus(self):
        mb = self.menuBar()
        A = self.actions
        m = mb.addMenu("파일(&F)")
        m.addActions([A["open_file"], A["open_folder"]])
        self.recent_menu = m.addMenu("최근 파일")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        m.addActions([A["reload"], A["open_location"], A["close_book"]])
        m.addSeparator()
        m.addAction(A["quit"])

        m = mb.addMenu("이동(&G)")
        for k in ("next_page", "prev_page", "next_single", "prev_single", "first_page", "last_page"):
            m.addAction(A[k])
        m.addSeparator()
        m.addActions([A["next_book"], A["prev_book"], A["goto_page"]])

        m = mb.addMenu("보기(&V)")
        m.addActions([A[k] for k in FIT_ACTIONS])
        m.addActions([A["zoom_in"], A["zoom_out"], A["toggle_upscale"]])
        m.addSeparator()
        m.addActions([A["toggle_two_page"], A["toggle_rtl"], A["toggle_cover"]])
        m.addSeparator()
        m.addActions([A["toggle_fullscreen"], A["toggle_thumbnails"], A["toggle_statusbar"],
                      A["toggle_info"], A["toggle_animation"]])

        m = mb.addMenu("책갈피(&B)")
        m.addActions([A["add_bookmark"], A["show_bookmarks"]])

        m = mb.addMenu("도구(&T)")
        m.addActions([A["settings"], A["shortcut_help"], A["check_update"], A["about"]])

    def _context_menu(self, pos):
        A = self.actions
        m = QMenu(self)
        m.addActions([A["open_file"], A["open_folder"]])
        m.addSeparator()
        m.addActions([A["next_book"], A["prev_book"], A["goto_page"]])
        m.addSeparator()
        fit = m.addMenu("맞춤")
        fit.addActions([A[k] for k in FIT_ACTIONS])
        m.addActions([A["toggle_two_page"], A["toggle_rtl"], A["toggle_fullscreen"], A["toggle_thumbnails"]])
        m.addSeparator()
        m.addActions([A["add_bookmark"], A["show_bookmarks"], A["open_location"]])
        m.addSeparator()
        m.addAction(A["settings"])
        m.exec(self.viewer.mapToGlobal(pos))

    def _fill_recent(self):
        self.recent_menu.clear()
        items = self.history.recent()
        if not items:
            a = self.recent_menu.addAction("(없음)")
            a.setEnabled(False)
            return
        for i, p in enumerate(items):
            a = self.recent_menu.addAction(f"&{(i + 1) % 10}  {os.path.basename(p.rstrip(chr(92) + '/')) or p}")
            a.setToolTip(p)
            a.setStatusTip(p)
            a.triggered.connect(lambda _c=False, path=p: self.open_any(path))
        self.recent_menu.addSeparator()
        clr = self.recent_menu.addAction("목록 지우기")
        clr.triggered.connect(self.history.clear_recent)

    # ================================================================ 설정 반영
    def apply_settings(self):
        v = self.viewer
        v.fit_mode = self.s["fit_mode"] if self.s["fit_mode"] in FIT_ACTIONS.values() else "window"
        v.rtl = bool(self.s["rtl"])
        v.upscale_small = bool(self.s["upscale_small"])
        v.smooth = bool(self.s["smooth"])
        v.wheel_mode = self.s["wheel_mode"]
        v.click_navigation = bool(self.s["click_navigation"])
        v.bg = QColor(self.s["background"])
        self.loader.max_mp = self.s["max_decode_megapixels"]
        self.cache.budget = int(self.s["cache_mb"]) * 1024 * 1024
        for aid, key in TOGGLE_ACTIONS.items():
            self.actions[aid].setChecked(bool(self.s[key]))
        for aid, mode in FIT_ACTIONS.items():
            self.actions[aid].setChecked(v.fit_mode == mode)
        self.dock.setVisible(bool(self.s["show_thumbnails"]))
        self.statusBar().setVisible(bool(self.s["show_statusbar"]))
        v.update()

    def _dock_visibility(self, visible):
        if self.isFullScreen():
            return
        self.s["show_thumbnails"] = visible
        self.actions["toggle_thumbnails"].setChecked(visible)

    def _restore_window(self):
        g = self.s["window_geometry"]
        if g:
            self.restoreGeometry(QByteArray.fromBase64(g.encode()))
        st = self.s["window_state"]
        if st:
            self.restoreState(QByteArray.fromBase64(st.encode()))
        self.dock.setVisible(bool(self.s["show_thumbnails"]))

    # ================================================================ 열기
    def open_any(self, path: str, start=None) -> bool:
        if not path:
            return False
        if not os.path.exists(path):
            QMessageBox.warning(self, APP_NAME, f"파일을 찾을 수 없습니다.\n{path}")
            return False
        return self.open_book(path, start)

    def open_book(self, path: str, start=None, password: str | None = None) -> bool:
        """start: None(이어보기/이미지 위치) | int | 'last' | ('name', 페이지이름, 예비 인덱스)"""
        try:
            book, s0 = open_path(path, password)
        except PasswordRequired:
            pw, ok = QInputDialog.getText(self, "비밀번호", f"압축 비밀번호를 입력하세요:\n{os.path.basename(path)}",
                                          QLineEdit.Password)
            if not ok:
                return False
            return self.open_book(path, start, pw)
        except (ArchiveError, ValueError, OSError) as e:
            QMessageBox.warning(self, APP_NAME, f"열 수 없습니다.\n{path}\n\n{e}")
            return False

        if len(book) == 0:
            book.close()
            if isinstance(book, FolderBook):
                child = self._first_child_book(book.path)
                if child:
                    return self.open_book(child, start)
            self.viewer.toast.show_text(f"이미지가 없습니다: {os.path.basename(path)}")
            return False

        self._remember_position()
        if self.book is not None:
            self.book.close()
        self.book = book
        self._boundary = None
        self.loader.set_book(book)
        self.thumbs.set_book(book)
        self.slider.setEnabled(True)
        self.slider.setMaximum(len(book))

        anchor = "start"
        resumed = False
        n = len(book)
        if start == "last":
            idx = last_start(n, self.s["two_page"], self.s["cover_single"], self._is_wide)
            anchor = "end"
        elif isinstance(start, tuple) and start and start[0] == "name":
            idx = book.index_of(start[1])
            if idx < 0:
                idx = min(max(0, int(start[2])), n - 1)
        elif isinstance(start, int):
            idx = start
        elif s0 is not None:
            idx = s0
        else:
            idx = 0
            pos = self.history.get_position(book.path) if self.s["resume_last_page"] else None
            if pos:
                j = book.index_of(pos.get("name", ""))
                idx = j if j >= 0 else min(int(pos.get("index", 0)), n - 1)
                resumed = idx > 0
        self.history.add_recent(book.path)
        self.s["last_dir"] = os.path.dirname(book.path)
        self.show_index(idx, anchor)
        if resumed:
            self.viewer.toast.show_text(f"{idx + 1}페이지부터 이어서 봅니다 (Home: 처음으로)", 2500)
        return True

    def _first_child_book(self, folder: str) -> str | None:
        try:
            entries = sorted(os.scandir(folder), key=lambda e: natural_key(e.name))
        except OSError:
            return None
        for e in entries:
            if e.is_file() and is_archive_name(e.name):
                return e.path
            if e.is_dir():
                if FolderBook(e.path).pages:
                    return e.path
        return None

    def _remember_position(self):
        if self.book is not None and len(self.book):
            i = min(self.index, len(self.book) - 1)
            self.history.set_position(self.book.path, i, self.book.pages[i].name, len(self.book))
            self._save_timer.start()

    # ================================================================ 표시
    def _is_wide(self, i: int) -> bool:
        if not self.s["wide_single"] or self.book is None or not (0 <= i < len(self.book)):
            return False
        d = self.loader.cached(i) or self.loader.get_sync(i)
        sz = d.orig_size if d.orig_size.isValid() else d.image.size()
        return sz.width() > sz.height() * 1.05

    def _spread(self, i):
        return spread_at(i, len(self.book), self.s["two_page"], self.s["cover_single"], self._is_wide)

    def show_index(self, i: int, anchor: str = "start"):
        if self.book is None or len(self.book) == 0:
            return
        n = len(self.book)
        i = max(0, min(i, n - 1))
        self._boundary = None
        spread = self._spread(i)
        pages = [PageImage(self.loader.get_sync(j), self.book.pages[j].name) for j in spread]
        self.index, self.spread = i, spread
        self.viewer.set_pages(pages, anchor)
        self.thumbs.set_current(i)
        self.slider.blockSignals(True)
        self.slider.setValue(i + 1)
        self.slider.blockSignals(False)
        self._update_status()
        self._remember_position()
        last = spread[-1]
        ahead = range(last + 1, last + 1 + int(self.s["preload_ahead"]))
        behind = range(max(0, i - int(self.s["preload_behind"])), i)
        self.loader.prefetch(list(ahead) + list(behind))

    def _update_status(self):
        if self.book is None:
            self.status_label.setText("")
            self.viewer.info_text = ""
            self.setWindowTitle(APP_NAME)
            return
        n = len(self.book)
        nums = "-".join(str(j + 1) for j in self.spread) or str(self.index + 1)
        parts, info = [], []
        for pi in self.viewer.pages:
            d = pi.dec
            sz = d.orig_size
            dims = f"{sz.width()}×{sz.height()}" if sz.isValid() else "?"
            extra = []
            if d.animated:
                fc = pi.player.frame_count() if pi.player else 0
                extra.append(f"애니메이션 {fc}프레임" if fc > 0 else "애니메이션")
            if d.downscaled:
                extra.append("축소 표시")
            fmt = (d.fmt or "").upper()
            parts.append(f"{pi.name.replace(chr(92), '/').rsplit('/', 1)[-1]}  {dims}  {fmt}  {human_size(d.byte_size)}"
                         + (f"  ({', '.join(extra)})" if extra else ""))
            info.append(f"{pi.name}\n{dims} · {fmt} · {human_size(d.byte_size)}" + (f" · {', '.join(extra)}" if extra else ""))
        zoom = f"{self.viewer.current_scale() * 100:.0f}%"
        mode = []
        if self.s["two_page"]:
            mode.append("두 페이지")
        if self.s["rtl"]:
            mode.append("RTL")
        self.status_label.setText(f"[{nums} / {n}]  " + "  |  ".join(parts) + f"  |  {zoom}"
                                  + (f"  |  {' · '.join(mode)}" if mode else ""))
        if self.s["info_overlay"]:
            self.viewer.info_text = (f"{self.book.title}  [{nums} / {n}]  {zoom}\n" + "\n".join(info)
                                     + f"\n{self.book.path}")
        else:
            self.viewer.info_text = ""
        self.viewer.update()
        self.setWindowTitle(f"{self.book.title} [{nums}/{n}] - {APP_NAME}")

    # ================================================================ 경계 처리
    def _boundary_pending(self, direction: int) -> bool:
        b = self._boundary
        return bool(b and b[0] == direction and time.monotonic() - b[2] < BOUNDARY_TIMEOUT)

    def _at_boundary(self, direction: int):
        mode = self.s["boundary_action"]
        word = "마지막" if direction > 0 else "첫"
        target = neighbor_book(self.book.path, direction) if mode != "stop" else None
        if mode == "stop":
            self.viewer.toast.show_text(f"{word} 페이지입니다")
            return
        if target is None:
            self.viewer.toast.show_text(f"{word} 페이지입니다\n({'다음' if direction > 0 else '이전'} 파일이 없어요)")
            return
        if mode == "auto":
            self.go_book(direction, target)
            return
        self._boundary = (direction, target, time.monotonic())
        self.viewer.toast.show_text(
            f"{word} 페이지예요. 한 번 더 넘기거나 Enter를 누르면\n"
            f"{'다음' if direction > 0 else '이전'} 파일로 이동: {os.path.basename(target)}",
            int(BOUNDARY_TIMEOUT * 1000))

    def go_book(self, direction: int, target: str | None = None) -> bool:
        if self.book is None:
            return False
        target = target or neighbor_book(self.book.path, direction)
        if not target:
            self.viewer.toast.show_text(f"{'다음' if direction > 0 else '이전'} 파일이 없어요")
            return False
        if direction > 0:
            start = 0
        else:
            start = "last" if self.s["prev_book_start"] == "last" else 0
        ok = self.open_book(target, start)
        if ok:
            self.viewer.toast.show_text(f"{'▶' if direction > 0 else '◀'} {os.path.basename(target)}", 1500)
        return ok

    # ================================================================ 액션 구현: 파일
    def act_open_file(self):
        exts = " ".join("*" + e for e in sorted(IMAGE_EXTS | set(ARCHIVE_EXTS)))
        path, _ = QFileDialog.getOpenFileName(
            self, "파일 열기", self.s["last_dir"] or "",
            f"이미지/압축 ({exts});;압축파일 ({' '.join('*' + e for e in ARCHIVE_EXTS)});;모든 파일 (*)")
        if path:
            self.open_any(path)

    def act_open_folder(self):
        d = QFileDialog.getExistingDirectory(self, "폴더 열기", self.s["last_dir"] or "")
        if d:
            self.open_any(d)

    def act_reload(self):
        if self.book is not None:
            path, idx = self.book.path, self.index
            self.cache.drop_book(path)
            self.open_book(path, idx)

    def act_open_location(self):
        if self.book is None:
            return
        target = self.book.path
        if self.book.kind == "folder" and self.book.pages:
            target = os.path.join(self.book.path, self.book.pages[self.index].name)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(target)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(target)))

    def act_close_book(self):
        self._remember_position()
        if self.book is not None:
            self.book.close()
        self.book = None
        self.loader.set_book(None)
        self.thumbs.set_book(None)
        self.viewer.clear()
        self.slider.setEnabled(False)
        self._update_status()

    def act_quit(self):
        self.close()

    # ================================================================ 액션 구현: 이동
    def act_next_page(self):
        if self.book is None:
            return
        if self._boundary_pending(+1):
            self.go_book(+1, self._boundary[1])
            return
        ni = (self.spread[-1] if self.spread else self.index) + 1
        if ni < len(self.book):
            self.show_index(ni)
        else:
            self._at_boundary(+1)

    def act_prev_page(self):
        if self.book is None:
            return
        if self._boundary_pending(-1):
            self.go_book(-1, self._boundary[1])
            return
        ps = prev_start(self.index, len(self.book), self.s["two_page"], self.s["cover_single"], self._is_wide)
        if ps is None:
            self._at_boundary(-1)
        else:
            self.show_index(ps, "end")

    def act_next_single(self):
        if self.book is not None:
            if self.index + 1 < len(self.book):
                self.show_index(self.index + 1)
            else:
                self._at_boundary(+1)

    def act_prev_single(self):
        if self.book is not None:
            if self.index > 0:
                self.show_index(self.index - 1, "end")
            else:
                self._at_boundary(-1)

    def act_scroll_down(self):
        if not self.viewer.scroll_step(+1):
            self.act_next_page()

    def act_scroll_up(self):
        if not self.viewer.scroll_step(-1):
            self.act_prev_page()

    def act_first_page(self):
        self.show_index(0)

    def act_last_page(self):
        if self.book is not None:
            self.show_index(last_start(len(self.book), self.s["two_page"], self.s["cover_single"], self._is_wide))

    def act_next_book(self):
        self.go_book(+1)

    def act_prev_book(self):
        self.go_book(-1)

    def act_confirm(self):
        if self._boundary and time.monotonic() - self._boundary[2] < BOUNDARY_TIMEOUT:
            d, target, _ = self._boundary
            self.go_book(d, target)

    def act_goto_page(self):
        if self.book is None:
            return
        n = len(self.book)
        v, ok = QInputDialog.getInt(self, "페이지로 이동", f"페이지 (1 ~ {n}):", self.index + 1, 1, n)
        if ok:
            self.show_index(v - 1)

    # ================================================================ 액션 구현: 보기
    def _set_fit(self, mode):
        self.s["fit_mode"] = mode
        self.viewer.set_fit_mode(mode)
        for aid, m in FIT_ACTIONS.items():
            self.actions[aid].setChecked(m == mode)
        self._update_status()

    def act_fit_window(self):
        self._set_fit("window")

    def act_fit_width(self):
        self._set_fit("width")

    def act_fit_height(self):
        self._set_fit("height")

    def act_fit_original(self):
        self._set_fit("original")

    def act_zoom_in(self):
        self.viewer.zoom_by(1.25)
        for a in FIT_ACTIONS:
            self.actions[a].setChecked(False)

    def act_zoom_out(self):
        self.viewer.zoom_by(0.8)
        for a in FIT_ACTIONS:
            self.actions[a].setChecked(False)

    def _toggle(self, aid):
        key = TOGGLE_ACTIONS[aid]
        self.s[key] = not self.s[key]
        self.actions[aid].setChecked(self.s[key])
        return self.s[key]

    def _redisplay(self):
        if self.book is not None:
            self.show_index(self.index)

    def act_toggle_two_page(self):
        on = self._toggle("toggle_two_page")
        self.viewer.toast.show_text("두 페이지 보기" if on else "한 페이지 보기", 1000)
        self._redisplay()

    def act_toggle_rtl(self):
        on = self._toggle("toggle_rtl")
        self.viewer.rtl = on
        self.viewer.toast.show_text("오른쪽 → 왼쪽 (만화)" if on else "왼쪽 → 오른쪽", 1000)
        self._redisplay()

    def act_toggle_cover(self):
        self._toggle("toggle_cover")
        self._redisplay()

    def act_toggle_upscale(self):
        self.viewer.upscale_small = self._toggle("toggle_upscale")
        self.viewer.update()
        self._update_status()

    def act_toggle_thumbnails(self):
        on = self._toggle("toggle_thumbnails")
        self.dock.setVisible(on)
        if on and self.book is not None:
            self.thumbs.set_current(self.index)

    def act_toggle_statusbar(self):
        self.statusBar().setVisible(self._toggle("toggle_statusbar"))

    def act_toggle_info(self):
        self._toggle("toggle_info")
        self._update_status()

    def act_toggle_animation(self):
        r = self.viewer.toggle_animation()
        if r is not None:
            self.viewer.toast.show_text("일시정지" if r else "재생", 800)

    def act_toggle_fullscreen(self):
        if self.isFullScreen():
            self._leave_fullscreen()
        else:
            self._fullscreen_restore = (self.menuBar().isVisible(), self.statusBar().isVisible(), self.dock.isVisible(),
                                        self.isMaximized())
            self.menuBar().hide()
            self.statusBar().hide()
            self.dock.hide()
            self.showFullScreen()
            self.actions["toggle_fullscreen"].setChecked(True)

    def _leave_fullscreen(self):
        mb, sb, dk, maxed = self._fullscreen_restore or (True, True, False, False)
        self.showMaximized() if maxed else self.showNormal()
        self.menuBar().setVisible(mb)
        self.statusBar().setVisible(sb)
        self.dock.setVisible(dk)
        self.actions["toggle_fullscreen"].setChecked(False)

    def act_escape(self):
        if self._boundary:
            self._boundary = None
            self.viewer.toast.hide()
        elif self.isFullScreen():
            self._leave_fullscreen()

    # ================================================================ 액션 구현: 책갈피
    def act_add_bookmark(self):
        if self.book is None:
            return
        default = f"{self.book.title} - {self.index + 1}p"
        title, ok = QInputDialog.getText(self, "책갈피 추가", "이름:", text=default)
        if not ok:
            return
        bm = Bookmark.from_book(self.book, self.index, title or default)
        self.bookmarks.add(bm)
        self.viewer.toast.show_text(f"책갈피 추가: {bm.title}")

    def act_show_bookmarks(self):
        dlg = BookmarksDialog(self.bookmarks, self)
        dlg.openRequested.connect(self.open_bookmark)
        dlg.exec()

    def open_bookmark(self, bm_id: str) -> bool:
        bm = self.bookmarks.get(bm_id)
        if bm is None:
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path, sure = relocate(bm, self.s["library_roots"], int(self.s["relocate_max_depth"]))
        finally:
            QApplication.restoreOverrideCursor()
        if path and not sure:
            r = QMessageBox.question(self, "책갈피", f"원래 위치에 파일이 없어요.\n이름이 같은 파일을 찾았는데 이걸로 열까요?\n\n{path}")
            if r != QMessageBox.Yes:
                path = None
        if path is None:
            r = QMessageBox.question(self, "책갈피",
                                     f"파일을 찾지 못했어요.\n{bm.location}\n\n직접 위치를 지정할까요?")
            if r != QMessageBox.Yes:
                return False
            if bm.book_kind == "folder":
                path = QFileDialog.getExistingDirectory(self, "폴더 선택")
            else:
                path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "압축파일 (*.*)")
            if not path:
                return False
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(bm.book_path):
            self.bookmarks.update_path(bm, path)
            QTimer.singleShot(0, lambda: self.viewer.toast.show_text("책갈피 경로를 새 위치로 고쳤어요", 2500))
        return self.open_book(path, ("name", bm.page_name, bm.page_index))

    # ================================================================ 액션 구현: 도구
    def act_settings(self):
        dlg = SettingsDialog(self.s, self)
        if dlg.exec():
            from ellview.ui.theme import apply_theme
            apply_theme(QApplication.instance(), self.s["theme"])
            self.reload_shortcuts()
            self.apply_settings()
            self._redisplay()

    def act_shortcut_help(self):
        HtmlDialog("단축키", shortcut_help_html(self.s["shortcuts"] or {}), self).exec()

    def act_about(self):
        HtmlDialog(f"{APP_NAME} 정보", about_html(), self).exec()

    def act_check_update(self):
        if not GITHUB_REPO:
            QMessageBox.information(self, "업데이트", "업데이트 저장소가 설정되지 않았습니다.\n(ellview/__init__.py의 GITHUB_REPO)")
            return
        self.statusBar().showMessage("업데이트 확인 중...", 3000)
        QThreadPool.globalInstance().start(_UpdateTask(self._upd_sig, True))

    def _on_update_result(self, info, manual):
        if info and updater.is_newer(info["version"]):
            self.update_label.setText(f'<a href="{info["url"]}">새 버전 {info["version"]} 받기</a>')
            if manual:
                r = QMessageBox.question(self, "업데이트", f"새 버전 {info['version']}이 있어요 (현재 {__version__}).\n"
                                         "다운로드 페이지를 열까요?")
                if r == QMessageBox.Yes:
                    QDesktopServices.openUrl(QUrl(info["url"]))
        elif manual:
            QMessageBox.information(self, "업데이트",
                                    "최신 버전을 사용 중이에요." if info else "업데이트 정보를 가져오지 못했어요.")

    # ================================================================ 종료
    def closeEvent(self, e):
        self._remember_position()
        if self.isFullScreen():
            self._leave_fullscreen()
        self.s["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.s["window_state"] = bytes(self.saveState().toBase64()).decode()
        try:
            self.s.save()
            self.history.save(force=True)
        except OSError:
            pass
        self.loader.pool.clear()
        self.thumbs.pool.clear()
        if self.book is not None:
            self.book.close()
        super().closeEvent(e)


__all__ = ["MainWindow", "sibling_books"]
