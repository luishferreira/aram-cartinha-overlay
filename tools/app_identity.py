"""A stable Windows taskbar identity and an icon shared by the app's windows."""
from pathlib import Path
from functools import lru_cache
import sys

APP_ID='AramCartinha.Overlay'


def set_app_id():
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes as W
        setter=ctypes.WinDLL('shell32').SetCurrentProcessExplicitAppUserModelID
        setter.argtypes=[W.LPCWSTR];setter.restype=ctypes.c_long
        if setter(APP_ID)<0:raise OSError('Could not set the Windows app identity')


def icon_path():
    if getattr(sys,'frozen',False):
        installed=Path(sys.executable).resolve().parent/'app.ico'
        if installed.is_file():return installed
    base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return base/'assets/app.ico'


@lru_cache(maxsize=1)
def native_api():
    import ctypes
    from ctypes import wintypes as W
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetAncestor.argtypes=[W.HWND,W.UINT];api.GetAncestor.restype=W.HWND
    api.LoadImageW.argtypes=[W.HINSTANCE,W.LPCWSTR,W.UINT,ctypes.c_int,ctypes.c_int,W.UINT]
    api.LoadImageW.restype=W.HANDLE
    api.SendMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];api.SendMessageW.restype=W.LPARAM
    api.GetSystemMetrics.argtypes=[ctypes.c_int];api.GetSystemMetrics.restype=ctypes.c_int
    return api


@lru_cache(maxsize=None)
def native_icon(path,width,height):
    # Keep the file-loaded HICON alive for the process lifetime, including remaps.
    # LR_SHARED must not be used with LR_LOADFROMFILE.
    import ctypes
    handle=native_api().LoadImageW(None,path,1,width,height,0x10)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    return handle


def apply_native_icons(window):
    api=native_api()
    hwnd=api.GetAncestor(window.winfo_id(),2) or window.winfo_id()
    icons={}
    for kind,metrics in ((0,(49,50)),(1,(11,12))):
        handle=native_icon(str(icon_path()),*(api.GetSystemMetrics(i) for i in metrics))
        api.SendMessageW(hwnd,0x80,kind,handle)  # WM_SETICON, ICON_SMALL / ICON_BIG
        icons[kind]=handle
    window._app_native_icons=icons


def native_icons_ready(window):
    """Check the actual wrapper HWND, not merely that an ICO file was decoded."""
    api=native_api()
    hwnd=api.GetAncestor(window.winfo_id(),2) or window.winfo_id()
    expected=getattr(window,'_app_native_icons',{})
    return len(expected)==2 and all(api.SendMessageW(hwnd,0x7f,kind,0)==handle for kind,handle in expected.items())


def apply_icon(window):
    if sys.platform!='win32':return
    window.iconbitmap(default=str(icon_path()))
    window.iconbitmap(str(icon_path()))
    apply_native_icons(window)
    if not getattr(window,'_app_icon_map_bound',False):
        def mapped(event):
            if event.widget==window:window.after_idle(lambda:apply_native_icons(window))
        window.bind('<Map>',mapped,add='+')
        window._app_icon_map_bound=True
