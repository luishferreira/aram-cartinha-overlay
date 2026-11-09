"""A stable Windows taskbar identity and an icon shared by the app's windows."""
from pathlib import Path
import sys

APP_ID='AramCartinha.Overlay'


def set_app_id():
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def icon_path():
    base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return base/'assets/app.ico'


def apply_icon(window):
    if sys.platform=='win32':window.iconbitmap(default=str(icon_path()))
