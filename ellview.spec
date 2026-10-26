# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정. 직접 실행보다는 `python scripts/build.py`를 쓰세요 (버전 정보/7-Zip 동봉/zip 생성까지 처리).
import os
import sys

ROOT = os.path.abspath(SPECPATH)
ICON = os.path.join(ROOT, "assets", "ellview.ico")
VERSION_FILE = os.path.join(ROOT, "build", "version_info.txt")

# 쓰지 않는 무거운 Qt 모듈 제외 → 용량 절약
EXCLUDES = [
    "tkinter", "unittest", "pydoc_data", "test", "numpy", "matplotlib", "IPython",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.Qt3DInput",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth", "PySide6.QtPositioning",
    "PySide6.QtLocation", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvgWidgets", "PySide6.QtNetworkAuth",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtHttpServer", "PySide6.QtConcurrent", "PySide6.QtDBus",
]

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "assets"), "assets")],
    hiddenimports=["pillow_heif", "py7zr", "rarfile", "PIL.AvifImagePlugin"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ellview",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON if sys.platform == "win32" else None,
    version=VERSION_FILE if (sys.platform == "win32" and os.path.exists(VERSION_FILE)) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Ellview")
