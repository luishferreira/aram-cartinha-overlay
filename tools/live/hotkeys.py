"""Deliver registered shortcuts through an owned Windows message-only window.

Tk dispatches thread messages before polling can see them. A window procedure
keeps WM_HOTKEY delivery intact, without hooks or keyboard input polling.
"""
import ctypes
from ctypes import wintypes as W
import os
from collections import deque


class OverlayHotkeys:
    def __init__(self):
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.actions = deque()
        self.registered = set()
        self.errors = {}
        self.hwnd = None
        self.callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        self.u.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        self.u.DefWindowProcW.restype = ctypes.c_ssize_t

        def receive(hwnd, message, wparam, lparam):
            if message == 0x312:  # WM_HOTKEY
                if int(wparam) in self.registered:
                    self.actions.append(int(wparam))
                return 0
            return self.u.DefWindowProcW(hwnd, message, wparam, lparam)

        self.callback = self.callback_type(receive)
        class WindowClass(ctypes.Structure):
            _fields_ = [("style", W.UINT), ("procedure", self.callback_type),
                        ("class_extra", ctypes.c_int), ("window_extra", ctypes.c_int),
                        ("instance", W.HINSTANCE), ("icon", W.HANDLE), ("cursor", W.HANDLE),
                        ("background", W.HANDLE), ("menu", W.LPCWSTR), ("name", W.LPCWSTR)]

        self.name = f"MayhemHotkeys_{os.getpid()}_{id(self)}"
        self.k.GetModuleHandleW.argtypes = [W.LPCWSTR]
        self.k.GetModuleHandleW.restype = W.HINSTANCE
        self.instance = self.k.GetModuleHandleW(None)
        self.window_class = WindowClass(procedure=self.callback, instance=self.instance, name=self.name)
        self.u.RegisterClassW.argtypes = [ctypes.POINTER(WindowClass)]
        self.u.RegisterClassW.restype = W.ATOM
        self.u.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
        self.u.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                                         ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                         W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
        self.u.CreateWindowExW.restype = W.HWND
        self.u.DestroyWindow.argtypes = [W.HWND]
        self.u.RegisterHotKey.argtypes = [W.HWND, ctypes.c_int, W.UINT, W.UINT]
        self.u.UnregisterHotKey.argtypes = [W.HWND, ctypes.c_int]
        if not self.u.RegisterClassW(ctypes.byref(self.window_class)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = self.u.CreateWindowExW(0, self.name, "", 0, 0, 0, 0, 0,
                                           W.HWND(-3), None, self.instance, None)
        if not self.hwnd:
            self.u.UnregisterClassW(self.name, self.instance)
            raise ctypes.WinError(ctypes.get_last_error())
        self.retry()

    def retry(self):
        for action, key in ((1, 0x77), (2, 0x78)):
            if action in self.registered:
                continue
            if self.u.RegisterHotKey(self.hwnd, action, 0x4002, key):  # Ctrl + no repeat
                self.registered.add(action)
                self.errors.pop(action, None)
            else:
                self.errors[action] = ctypes.get_last_error()

    def drain(self):
        while self.actions:
            yield self.actions.popleft()

    def close(self):
        if self.hwnd:
            for action in self.registered:
                self.u.UnregisterHotKey(self.hwnd, action)
            self.registered.clear()
            self.u.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.u.UnregisterClassW(self.name, self.instance)
