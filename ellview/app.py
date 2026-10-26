from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ellview import APP_NAME, __version__
from ellview.config import Settings, app_base_dir, data_dir


def _install_excepthook():
    """창 모드 exe에서는 콘솔이 없으므로 예기치 못한 오류를 로그 파일과 메시지로 알려줍니다."""
    log = data_dir() / "error.log"

    def hook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"--- {APP_NAME} {__version__}\n{text}\n")
        except OSError:
            pass
        sys.__excepthook__(etype, value, tb)
        if QApplication.instance() is not None:
            QMessageBox.critical(None, APP_NAME, f"예기치 못한 오류가 발생했어요.\n로그: {log}\n\n{value}")

    sys.excepthook = hook


def _icon() -> QIcon:
    for base in (app_base_dir() / "assets", app_base_dir() / "_internal" / "assets",
                 getattr(sys, "_MEIPASS", "") and os.path.join(sys._MEIPASS, "assets")):
        if not base:
            continue
        p = os.path.join(str(base), "ellview.ico")
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _install_excepthook()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(_icon())
    # Qt 기본 대화상자(확인/취소 등) 한국어화
    tr = QTranslator(app)
    if tr.load(QLocale(QLocale.Korean), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)

    from ellview.core.archives import cleanup_cache
    from ellview.ui.main_window import MainWindow
    from ellview.ui.theme import apply_theme

    settings = Settings()
    apply_theme(app, settings["theme"])
    cleanup_cache()
    win = MainWindow(settings)
    win.show()
    if settings["shell_menu"]:
        # exe를 다른 폴더로 옮겼으면 탐색기 메뉴의 실행 경로를 지금 위치로 갱신
        try:
            from ellview.core import shell_menu
            shell_menu.ensure_current()
        except OSError:
            pass
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args:
        win.open_any(os.path.abspath(args[0]))
    if "--smoke-test" in argv:
        # 빌드 검증용: 잠깐 띄웠다가 상태를 파일로 남기고 종료 (CI에서 exe 동작 확인)
        from PySide6.QtCore import QTimer

        def finish():
            info = {"version": __version__, "book": win.book.path if win.book else None,
                    "pages": len(win.book) if win.book else 0,
                    "first_ok": bool(win.viewer.pages and win.viewer.pages[0].dec.error is None)}
            import json
            (data_dir() / "smoke.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            win.close()
            app.quit()
        QTimer.singleShot(1500, finish)
    return app.exec()
