import ctypes
import gc
from ctypes import wintypes as W
import os
import time
import unittest


@unittest.skipUnless(os.name == "nt", "Windows shortcut integration")
class HotkeyDeliveryTests(unittest.TestCase):
    def test_registered_messages_survive_the_tk_event_loop(self):
        import tkinter as tk
        from tools.live.hotkeys import OverlayHotkeys
        root = tk.Tk()
        root.withdraw()
        shortcuts = OverlayHotkeys()
        try:
            if shortcuts.registered != {1, 2}:
                self.skipTest("Shortcuts currently owned by another application")
            user = ctypes.WinDLL("user32")
            user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
            for action in (1, 2):
                self.assertTrue(user.PostMessageW(shortcuts.hwnd, 0x312, action, 0))
            deadline = time.monotonic()+.5
            while len(shortcuts.actions)<2 and time.monotonic()<deadline:
                root.update()
            self.assertEqual(list(shortcuts.drain()), [1, 2])
            self.assertEqual(list(shortcuts.drain()), [])
        finally:
            shortcuts.close()
            root.destroy()
            root = None
            gc.collect()  # Keep Tcl finalization on the thread that created the window.

    def test_shortcuts_can_be_retried_after_a_conflicting_instance_closes(self):
        from tools.live.hotkeys import OverlayHotkeys
        first = OverlayHotkeys()
        second = None
        try:
            if first.registered != {1, 2}:
                self.skipTest("Shortcuts currently owned by another application")
            second = OverlayHotkeys()
            self.assertEqual(second.registered, set())
            self.assertEqual(set(second.errors), {1, 2})
            first.close()
            second.retry()
            self.assertEqual(second.registered, {1, 2})
            self.assertEqual(second.errors, {})
        finally:
            first.close()
            if second:
                second.close()
