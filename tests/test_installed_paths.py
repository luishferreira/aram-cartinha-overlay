import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools.app_paths import app_root,local_root
from tools.system_process import run,child_environment


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

    def test_unrelated_path_mount_is_not_resolved_or_modified(self):
        original={'PATH':os.pathsep.join(['C:/Windows/System32','C:/nvm4w/nodejs',
                                         'C:/Apps/Overlay/_internal','C:/Apps/Overlay/_internal/numpy.libs']),
                  'EXAMPLE':'preserved'}
        with patch.object(Path,'resolve',side_effect=OSError(448,'Untrusted mount point')):
            clean=child_environment(original,'C:/Apps/Overlay/_internal')
        self.assertEqual(clean['PATH'],os.pathsep.join(['C:/Windows/System32','C:/nvm4w/nodejs']))
        self.assertEqual(clean['EXAMPLE'],'preserved')
        self.assertIn('numpy.libs',original['PATH'])

    def test_child_path_filter_uses_boundaries_not_shared_name_prefix(self):
        original={'PATH':os.pathsep.join(['C:/App/_internal-other','D:/tools',
                                         '"c:\\APP\\_internal\\lib"','.'])}
        clean=child_environment(original,'C:/App/_internal')
        self.assertEqual(clean['PATH'],os.pathsep.join(['C:/App/_internal-other','D:/tools','.']))

    def test_source_can_explicitly_share_existing_installed_profile_for_recovery(self):
        with patch.object(sys,'frozen',False,create=True),patch.dict(os.environ,{'ARAM_CARTINHA_USER_DIR':'C:/tests/existing-profile'}):
            self.assertEqual(local_root(),Path('C:/tests/existing-profile'))

    def test_system_process_returns_output_and_preserves_nonzero_status(self):
        with patch.object(sys,'frozen',False,create=True):
            result=run([sys.executable,'-c','import sys; print("ok"); sys.exit(3)'],capture_output=True,text=True)
            self.assertEqual(result.returncode,3)
            self.assertEqual(result.stdout.strip(),'ok')
            with self.assertRaises(subprocess.CalledProcessError):
                run([sys.executable,'-c','raise SystemExit(3)'],check=True)


if __name__=='__main__':
    unittest.main()
