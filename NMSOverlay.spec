# -*- mode: python -*-
# Build unico (onefile) do NMS Overlay. Gere com:  pyinstaller NMSOverlay.spec
a = Analysis(
    ['nms_overlay.py'],
    pathex=[],
    binaries=[],
    datas=[('checklist', 'checklist')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['test_overlay'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='NMS-Overlay',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
