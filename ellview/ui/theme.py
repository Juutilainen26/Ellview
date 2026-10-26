from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, theme: str):
    app.setStyle("Fusion")
    if theme == "light":
        app.setPalette(app.style().standardPalette())
        return
    if theme == "system":
        app.setPalette(QPalette())
        return
    p = QPalette()
    base, alt, text = QColor(32, 33, 36), QColor(43, 44, 48), QColor(230, 230, 230)
    p.setColor(QPalette.Window, alt)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, alt)
    p.setColor(QPalette.ToolTipBase, QColor(50, 50, 55))
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, alt)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.Highlight, QColor(94, 129, 244))
    p.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.Link, QColor(120, 160, 255))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(120, 120, 120))
    app.setPalette(p)
