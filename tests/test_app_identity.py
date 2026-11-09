"""Exercise native window icons through mapping and Tk wrapper recreation."""
import sys
import tkinter as tk
import unittest

from tools.app_identity import apply_icon,native_icons_ready,set_app_id


@unittest.skipUnless(sys.platform=='win32','Windows window icons')
class AppIconTests(unittest.TestCase):
    def test_native_small_and_large_icons_survive_window_remapping(self):
        set_app_id()
        root=tk.Tk();root.withdraw()
        try:
            window=tk.Toplevel(root);window.attributes('-alpha',0)
            apply_icon(window)
            root.update()
            self.assertTrue(native_icons_ready(window))
            window.withdraw();root.update()
            window.deiconify();root.update()
            self.assertTrue(native_icons_ready(window))
        finally:root.destroy()

    def test_hidden_root_has_explicit_icons_before_it_is_shown(self):
        root=tk.Tk();root.withdraw()
        try:
            apply_icon(root)
            self.assertTrue(native_icons_ready(root))
        finally:root.destroy()
