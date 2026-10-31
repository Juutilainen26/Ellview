from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from ellview import APP_NAME, __version__
from ellview.ui.shortcuts import ACTIONS, keys_for


# ======================================================================= 책갈피
class BookmarksDialog(QDialog):
    openRequested = Signal(str)  # bookmark id

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("책갈피")
        self.resize(820, 420)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["이름", "위치 (경로 > 페이지)", "페이지", "추가한 날"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 200)
        self.table.doubleClicked.connect(lambda _: self._open())
        lay.addWidget(self.table)
        hint = QLabel("빨간색 항목은 원래 경로에 파일이 없어요. 열면 라이브러리 폴더와 상위 폴더에서 자동으로 찾아봅니다.")
        hint.setStyleSheet("color:gray")
        lay.addWidget(hint)
        row = QHBoxLayout()
        for text, fn in (("열기", self._open), ("이름 바꾸기", self._rename),
                         ("경로 복사", self._copy), ("삭제", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("닫기")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for bm in self.store.items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            exists = os.path.exists(bm.book_path)
            cells = [bm.title, bm.location, f"{bm.page_index + 1} / {bm.page_count}",
                     time.strftime("%Y-%m-%d %H:%M", time.localtime(bm.created))]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, bm.id)
                it.setToolTip(bm.location)
                if not exists:
                    it.setForeground(QColor(230, 110, 110))
                self.table.setItem(r, c, it)

    def _selected_id(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        return self.table.item(r, 0).data(Qt.UserRole)

    def _open(self):
        bid = self._selected_id()
        if bid:
            self.openRequested.emit(bid)
            self.accept()

    def _rename(self):
        bid = self._selected_id()
        bm = self.store.get(bid) if bid else None
        if not bm:
            return
        text, ok = QInputDialog.getText(self, "이름 바꾸기", "책갈피 이름:", text=bm.title)
        if ok:
            bm.title = text
            self.store.save()
            self.refresh()

    def _copy(self):
        bid = self._selected_id()
        bm = self.store.get(bid) if bid else None
        if bm:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(bm.location)

    def _delete(self):
        bid = self._selected_id()
        if bid and QMessageBox.question(self, "삭제", "이 책갈피를 삭제할까요?") == QMessageBox.Yes:
            self.store.remove(bid)
            self.refresh()


# ======================================================================= 설정
def _combo(options, current):
    c = QComboBox()
    for value, label in options:
        c.addItem(label, value)
    i = c.findData(current)
    c.setCurrentIndex(max(0, i))
    return c


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("설정")
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # --- 일반
        g = QWidget()
        f = QFormLayout(g)
        self.boundary = _combo([("stop", "넘어가지 않고 알림만 (파일 이동은 [ ] 키)"),
                                ("prompt", "안내 후 한 번 더 넘기면 이동"), ("auto", "바로 옆 파일로 이동")],
                               settings["boundary_action"])
        f.addRow("휠·방향키로 처음/끝을 넘길 때", self.boundary)
        self.prev_start = _combo([("last", "마지막 페이지부터"), ("first", "첫 페이지부터")], settings["prev_book_start"])
        f.addRow("  └ 뒤로 넘겨 이전 파일로 갈 때", self.prev_start)
        self.boundary.currentIndexChanged.connect(
            lambda _i: self.prev_start.setEnabled(self.boundary.currentData() != "stop"))
        self.prev_start.setEnabled(settings["boundary_action"] != "stop")
        self.resume = QCheckBox("다시 열면 마지막으로 보던 페이지부터")
        self.resume.setChecked(settings["resume_last_page"])
        f.addRow(self.resume)
        self.wheel = _combo([("page", "페이지 넘기기 (넘치면 스크롤 후 넘김)"), ("scroll", "스크롤만")], settings["wheel_mode"])
        f.addRow("마우스 휠", self.wheel)
        self.click_nav = QCheckBox("화면 양 끝 가운데(가로 5분의 1 × 세로 30%) 클릭으로 페이지 이동")
        self.click_nav.setChecked(settings["click_navigation"])
        f.addRow(self.click_nav)
        self.updates = QCheckBox("시작할 때 업데이트 확인")
        self.updates.setChecked(settings["check_updates"])
        f.addRow(self.updates)
        self.slide_iv = QDoubleSpinBox()
        self.slide_iv.setRange(0.5, 120.0)
        self.slide_iv.setSingleStep(0.5)
        self.slide_iv.setDecimals(1)
        self.slide_iv.setSuffix(" 초")
        self.slide_iv.setValue(float(settings["slideshow_interval"]))
        f.addRow("슬라이드쇼 간격", self.slide_iv)
        self.slide_end = _combo([("next_book", "다음 파일로 이어서"), ("loop", "처음 페이지부터 반복"),
                                 ("stop", "멈춤")], settings["slideshow_end"])
        f.addRow("슬라이드쇼가 책 끝에 닿으면", self.slide_end)
        from ellview.core import shell_menu
        self.shell = QCheckBox("탐색기 우클릭 메뉴에 'Ellview로 열기' 추가 (폴더 · 이미지 · 압축파일)")
        self.shell.setChecked(bool(settings["shell_menu"]))
        if not shell_menu.supported():
            self.shell.setEnabled(False)
            self.shell.setToolTip("Windows에서만 사용할 수 있어요")
        f.addRow(self.shell)
        tabs.addTab(g, "일반")

        # --- 보기
        v = QWidget()
        f2 = QFormLayout(v)
        self.theme = _combo([("dark", "어둡게"), ("light", "밝게"), ("system", "시스템")], settings["theme"])
        f2.addRow("테마 (재시작 시 완전 적용)", self.theme)
        self.bg_btn = QPushButton(settings["background"])
        self._bg = settings["background"]
        self.bg_btn.clicked.connect(self._pick_bg)
        self._paint_bg_btn()
        f2.addRow("배경색", self.bg_btn)
        self.smooth = QCheckBox("부드럽게 확대/축소")
        self.smooth.setChecked(settings["smooth"])
        f2.addRow(self.smooth)
        self.upscale = QCheckBox("창보다 작은 이미지도 맞춤 크기로 확대")
        self.upscale.setChecked(settings["upscale_small"])
        f2.addRow(self.upscale)
        self.cover = QCheckBox("두 페이지 보기에서 첫 장은 단독 (표지)")
        self.cover.setChecked(settings["cover_single"])
        f2.addRow(self.cover)
        self.wide = QCheckBox("두 페이지 보기에서 가로로 긴 이미지는 단독")
        self.wide.setChecked(settings["wide_single"])
        f2.addRow(self.wide)
        self.ahead = QSpinBox()
        self.ahead.setRange(0, 20)
        self.ahead.setValue(settings["preload_ahead"])
        f2.addRow("앞쪽 미리 읽기 (장)", self.ahead)
        self.cache = QSpinBox()
        self.cache.setRange(64, 8192)
        self.cache.setSingleStep(64)
        self.cache.setValue(settings["cache_mb"])
        f2.addRow("이미지 캐시 (MB)", self.cache)
        self.maxmp = QSpinBox()
        self.maxmp.setRange(10, 2000)
        self.maxmp.setValue(settings["max_decode_megapixels"])
        f2.addRow("이보다 큰 사진은 축소해서 열기 (메가픽셀)", self.maxmp)
        tabs.addTab(v, "보기")

        # --- 책갈피 폴더
        lb = QWidget()
        lv = QVBoxLayout(lb)
        lv.addWidget(QLabel("책갈피한 파일을 옮겼을 때 여기 등록한 폴더(하위 폴더 포함)에서 찾아봅니다.\n"
                            "만화/사진을 모아두는 최상위 폴더를 등록해 두면 좋아요."))
        self.roots = QListWidget()
        self.roots.addItems(settings["library_roots"])
        lv.addWidget(self.roots)
        rb = QHBoxLayout()
        add = QPushButton("폴더 추가")
        add.clicked.connect(self._add_root)
        rm = QPushButton("선택 삭제")
        rm.clicked.connect(lambda: self.roots.takeItem(self.roots.currentRow()))
        rb.addWidget(add)
        rb.addWidget(rm)
        rb.addStretch(1)
        lv.addLayout(rb)
        tabs.addTab(lb, "책갈피 폴더")

        # --- 단축키
        sk = QWidget()
        sv = QVBoxLayout(sk)
        sv.addWidget(QLabel("단축키 칸을 더블클릭해서 수정하세요. 여러 개는 쉼표(,)로 구분합니다. 예: Right, PgDown"))
        self.keys = QTableWidget(len(ACTIONS), 3)
        self.keys.setHorizontalHeaderLabels(["분류", "동작", "단축키"])
        self.keys.verticalHeader().setVisible(False)
        self.keys.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        overrides = settings["shortcuts"] or {}
        for r, (aid, label, _d, cat) in enumerate(ACTIONS):
            for c, text in enumerate((cat, label, ", ".join(keys_for(aid, overrides)))):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, aid)
                if c < 2:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.keys.setItem(r, c, it)
        sv.addWidget(self.keys)
        reset = QPushButton("모두 기본값으로")
        reset.clicked.connect(self._reset_keys)
        sv.addWidget(reset, alignment=Qt.AlignLeft)
        tabs.addTab(sk, "단축키")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _paint_bg_btn(self):
        self.bg_btn.setText(self._bg)
        self.bg_btn.setStyleSheet(f"background:{self._bg}; color:{'#000' if QColor(self._bg).lightness() > 128 else '#fff'}")

    def _pick_bg(self):
        c = QColorDialog.getColor(QColor(self._bg), self, "배경색")
        if c.isValid():
            self._bg = c.name()
            self._paint_bg_btn()

    def _add_root(self):
        d = QFileDialog.getExistingDirectory(self, "라이브러리 폴더 선택")
        if d:
            self.roots.addItem(os.path.abspath(d))

    def _reset_keys(self):
        for r, (aid, _l, defaults, _c) in enumerate(ACTIONS):
            self.keys.item(r, 2).setText(", ".join(defaults))

    def _collect_keys(self):
        result, used, bad = {}, {}, []
        for r, (aid, label, defaults, _c) in enumerate(ACTIONS):
            raw = self.keys.item(r, 2).text()
            ks = [k.strip() for k in raw.split(",") if k.strip()]
            norm = []
            for k in ks:
                seq = QKeySequence(k)
                if seq.isEmpty():
                    bad.append(f"{label}: {k}")
                    continue
                t = seq.toString()
                if t in used:
                    bad.append(f"'{t}' 중복: {used[t]} / {label}")
                used[t] = label
                norm.append(t)
            if norm != [QKeySequence(d).toString() for d in defaults]:
                result[aid] = norm
        return result, bad

    def _accept(self):
        keys, bad = self._collect_keys()
        if bad:
            QMessageBox.warning(self, "단축키 확인", "다음 단축키를 확인해 주세요:\n\n" + "\n".join(bad[:15]))
            return
        s = self.s
        s["boundary_action"] = self.boundary.currentData()
        s["prev_book_start"] = self.prev_start.currentData()
        s["resume_last_page"] = self.resume.isChecked()
        s["wheel_mode"] = self.wheel.currentData()
        s["click_navigation"] = self.click_nav.isChecked()
        s["check_updates"] = self.updates.isChecked()
        s["slideshow_interval"] = round(self.slide_iv.value(), 1)
        s["slideshow_end"] = self.slide_end.currentData()
        if self.shell.isEnabled():
            s["shell_menu"] = self.shell.isChecked()
        s["theme"] = self.theme.currentData()
        s["background"] = self._bg
        s["smooth"] = self.smooth.isChecked()
        s["upscale_small"] = self.upscale.isChecked()
        s["cover_single"] = self.cover.isChecked()
        s["wide_single"] = self.wide.isChecked()
        s["preload_ahead"] = self.ahead.value()
        s["cache_mb"] = self.cache.value()
        s["max_decode_megapixels"] = self.maxmp.value()
        s["library_roots"] = [self.roots.item(i).text() for i in range(self.roots.count())]
        s["shortcuts"] = keys
        s.save()
        self.accept()


# ======================================================================= 도움말
def shortcut_help_html(overrides: dict) -> str:
    rows = []
    cat = None
    for aid, label, _d, c in ACTIONS:
        if c != cat:
            rows.append(f"<tr><td colspan=2 style='padding-top:10px'><b>{c}</b></td></tr>")
            cat = c
        ks = ", ".join(keys_for(aid, overrides)) or "-"
        rows.append(f"<tr><td style='padding-right:24px'>{label}</td><td><code>{ks}</code></td></tr>")
    extra = ("<p><b>마우스</b><br>휠: 페이지 이동 (넘치는 이미지는 스크롤 후 이동) · Ctrl+휠: 확대/축소<br>"
             "화면 양 끝 5분의 1 칸의 세로 가운데 영역 클릭: 이전/다음 (마우스를 올리면 화살표 표시)<br>"
             "가운데 끌기: 이동 · 가운데 더블클릭: 전체 화면 · 오른쪽 클릭: 메뉴<br>"
             "파일/폴더를 창에 끌어다 놓으면 바로 열립니다.</p>")
    return f"<h3>{APP_NAME} 단축키</h3><table>{''.join(rows)}</table>{extra}"


class HtmlDialog(QDialog):
    def __init__(self, title, html, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 640)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(html)
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


def about_html() -> str:
    return (f"<h2>{APP_NAME} {__version__}</h2>"
            "<p>가볍고 빠른 이미지 · 만화 뷰어</p>"
            "<ul><li>폴더 / ZIP · CBZ / 7Z · CB7 / RAR · CBR / TAR</li>"
            "<li>JPG · PNG · GIF · WebP · APNG · AVIF · HEIC · BMP · TIFF · PSD 등</li>"
            "<li>움직이는 GIF/WebP/APNG, 초대형 이미지 축소 디코딩</li></ul>"
            "<p>Python · PySide6(Qt) · Pillow 기반</p>")
