"""Windows window metadata and passive mouse sampling; no hooks or injected code."""
import ctypes
from ctypes import wintypes as W
import os
import time


class WindowsHost:
    def __init__(self, exclude_from_capture=False):
        if os.name != "nt":
            raise RuntimeError("Este debug requer Windows")
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.exclude_from_capture = exclude_from_capture
        self.capture_exclusions = {}
        self.u.SetWindowDisplayAffinity.argtypes = [W.HWND, W.DWORD]
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u.GetForegroundWindow.restype = W.HWND
        self.u.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        self.u.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        self.u.ClientToScreen.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
        self.u.ScreenToClient.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
        self.u.GetCursorPos.argtypes = [ctypes.POINTER(W.POINT)]
        self.u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.u.GetAsyncKeyState.restype = ctypes.c_short
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        self.k.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.u.GetAncestor.argtypes = [W.HWND, W.UINT]
        self.u.GetAncestor.restype = W.HWND
        self.u.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
        self.u.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
        self.u.SetProcessDpiAwarenessContext.argtypes = [W.HANDLE]
        self.u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.cached = None
        self.cached_at = 0
        self.left_down = False

    def foreground_game(self):
        hwnd = self.u.GetForegroundWindow()
        if not hwnd:
            return None
        if self.cached and self.cached["hwnd"] == hwnd and time.monotonic() - self.cached_at < 2:
            return self.cached
        pid = W.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = self.k.OpenProcess(0x1000, False, pid.value)
        if not process:
            return None
        try:
            path, size = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
            if not self.k.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)):
                return None
            if os.path.basename(path.value).lower() != "league of legends.exe":
                return None
            created, exited, kernel, user = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
            if not self.k.GetProcessTimes(process, *[ctypes.byref(v) for v in (created, exited, kernel, user)]):
                return None
            rect, point = W.RECT(), W.POINT(0, 0)
            if not self.u.GetClientRect(hwnd, ctypes.byref(rect)) or not self.u.ClientToScreen(hwnd, ctypes.byref(point)):
                return None
            self.cached = {"hwnd": hwnd, "pid": pid.value,
                "process_start": (created.dwHighDateTime << 32) | created.dwLowDateTime,
                "x": point.x, "y": point.y, "width": rect.right, "height": rect.bottom}
            self.cached_at = time.monotonic()
            return self.cached
        finally:
            self.k.CloseHandle(process)

    def poll_click(self, game):
        # Only the current physical primary button's high bit is used, never keystroke text.
        button = 2 if self.u.GetSystemMetrics(23) else 1
        down = bool(self.u.GetAsyncKeyState(button) & 0x8000)
        edge = down and not self.left_down
        self.left_down = down
        if not edge or not game:
            return None
        point = W.POINT()
        if not self.u.GetCursorPos(ctypes.byref(point)) or not self.u.ScreenToClient(game["hwnd"], ctypes.byref(point)):
            return None
        if 0 <= point.x < game["width"] and 0 <= point.y < game["height"]:
            return point.x, point.y
        return None

    def cursor_position(self, game):
        """Position only, to associate an already visible tooltip with self's cell."""
        point = W.POINT()
        if self.u.GetCursorPos(ctypes.byref(point)) and self.u.ScreenToClient(game["hwnd"], ctypes.byref(point)):
            return point.x, point.y
        return None

    def make_overlay(self, tk_window_id, show=True, interactive=False):
        hwnd = self.u.GetAncestor(tk_window_id, 2) or tk_window_id
        getter = self.u.GetWindowLongPtrW
        setter = self.u.SetWindowLongPtrW
        getter.argtypes, getter.restype = [W.HWND, ctypes.c_int], ctypes.c_ssize_t
        setter.argtypes, setter.restype = [W.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t
        style = getter(hwnd, -20) | 0x80000 | 0x08000000 | 0x80
        # Own UI controls receive ordinary window clicks, without activating the
        # window or monitoring/injecting inputs into the game. Data stays passive.
        style = (style & ~0x20) if interactive else (style | 0x20)
        setter(hwnd, -20, style)
        if self.exclude_from_capture:
            self.capture_exclusions[int(hwnd)] = bool(self.u.SetWindowDisplayAffinity(hwnd, 0x11))
        if show:
            self.u.ShowWindow(hwnd, 8)  # SW_SHOWNA
            self.u.SetWindowPos(hwnd, W.HWND(-1), 0, 0, 0, 0, 0x1 | 0x2 | 0x10)
        return hwnd
