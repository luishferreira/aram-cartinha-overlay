import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools.app_paths import app_root,local_root
from tools.system_process import run


class InstalledPathTests(unittest.TestCase):
    def test_source_execution_keeps_existing_local_directory(self):
        with patch.object(sys,'frozen',False,create=True):
            root=Path('C:/workspace/example')
            self.assertEqual(local_root(root),root/'data/local')

    def test_frozen_resources_resolve_beside_executable(self):
        executable=Path('C:/Apps/Aram Cartinha/AramCartinhaOverlay.exe')
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(executable)):
            self.assertEqual(app_root(),executable.resolve().parent)

    def test_installed_user_data_is_outside_program_directory(self):
        with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'LOCALAPPDATA':'C:/Users/example/AppData/Local'},clear=True):
            folder=local_root(Path('C:/Apps/AramCartinhaOverlay'))
            self.assertEqual(folder,Path('C:/Users/example/AppData/Local/AramCartinhaOverlay'))
            self.assertFalse(folder.is_relative_to(Path('C:/Apps/AramCartinhaOverlay')))

    def test_explicit_test_profile_is_absolute_and_keeps_state_separate(self):
        with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'ARAM_CARTINHA_USER_DIR':'C:/tests/profile'},clear=True):
            self.assertEqual(local_root(),Path('C:/tests/profile'))
        with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'ARAM_CARTINHA_USER_DIR':'relative/profile'},clear=True):
            with self.assertRaises(ValueError):local_root()

    def test_missing_windows_profile_is_reported(self):
        with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):local_root()

    def test_system_process_returns_output_and_preserves_nonzero_status(self):
        with patch.object(sys,'frozen',False,create=True):
            result=run([sys.executable,'-c','import sys; print("ok"); sys.exit(3)'],capture_output=True,text=True)
            self.assertEqual(result.returncode,3)
            self.assertEqual(result.stdout.strip(),'ok')
            with self.assertRaises(subprocess.CalledProcessError):
                run([sys.executable,'-c','raise SystemExit(3)'],check=True)


if __name__=='__main__':
    unittest.main()
