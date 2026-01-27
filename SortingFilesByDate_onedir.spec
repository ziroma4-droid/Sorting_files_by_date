# -*- mode: python ; coding: utf-8 -*-
# Сборка в папку (onedir). Только QtCore/Gui/Widgets — без WebEngine, 3D, QML, переводов и т.п.

from PyInstaller.utils.hooks import collect_all

# Оставляем только то, что нужно для QtWidgets: Core, Gui, Widgets + plugins/platforms, styles
_EXCLUDE = (
    'QtWebEngine', 'Qt3D', 'QtCharts', 'QtMultimedia', 'QtQml', 'QtQuick',
    'QtNetwork', 'QtSql', 'QtSvg', 'QtBluetooth', 'QtPositioning', 'QtDesigner',
    'QtDataVisualization', 'QtPdf', 'QtHttpServer', 'QtWebChannel', 'QtWebSockets',
    'QtScxml', 'QtSensors', 'QtStateMachine', 'QtHelp', 'QtOpenGL', 'QtPrintSupport',
    'QtTest', 'QtUiTools', 'QtDBus', 'QtMqtt', 'QtNfc', 'QtOpcUa', 'QtCoap',
    'QtRemoteObjects', 'QtLocation', 'QtSerialBus', 'QtSerialPort', 'QtTextToSpeech',
    'translations', 'wayland', 'xcbglintegrations', 'virtualkeyboard', 'iconengines',
)

def _filter_toc(toc_list, exclude):
    if toc_list is None:
        return []
    out = []
    for item in toc_list:
        name = item[0] if isinstance(item[0], str) else str(item[0])
        if not any(x in name.replace('\\', '/') for x in exclude):
            out.append(item)
    return out

tmp = collect_all("PySide6")
datas = _filter_toc(tmp[0], _EXCLUDE)
binaries = _filter_toc(tmp[1], _EXCLUDE)
# Только нужные модули — не тянем весь tmp[2] из collect_all
hiddenimports = [
    "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "shiboken6",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SortingFilesByDate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SortingFilesByDate",
)
