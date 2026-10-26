from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import Qt
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

    from ellview.core.archives import cleanup_cache
    from ellview.ui.main_window import MainWindow
    from ellview.ui.theme import apply_theme

    settings = Settings()
    apply_theme(app, settings["theme"])
    cleanup_cache()
    win = MainWindow(settings)
    win.show()
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args:
        win.open_any(os.path.abspath(args[0]))
    return app.exec()
