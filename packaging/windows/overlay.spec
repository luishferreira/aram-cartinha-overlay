# Build with the dedicated environment: python -m PyInstaller packaging/windows/overlay.spec
from pathlib import Path
import sys

root = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0,str(root))
from tools.version import APP_NAME

a = Analysis(
    [str(root/'tools/release/windows_entry.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root/'tools/live/ocr_server.ps1'),'tools/live'),
           (str(root/'tools/live/capture_game.ps1'),'tools/live'),
           (str(root/'assets/app.ico'),'assets')],
    hiddenimports=['tools.live.visual_collector','PIL.ImageGrab','PIL.ImageFont','numpy'],
    hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['pytest','unittest','pip','setuptools'],noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='AramCartinhaOverlay',
          debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
          console=False,disable_windowed_traceback=False,
          version=str(root/'packaging/windows/version-info.txt'),
          icon=str(root/'assets/app.ico'),
          uac_admin=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='AramCartinhaOverlay')
