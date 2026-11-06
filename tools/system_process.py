"""Start OS utilities without inheriting PyInstaller's DLL directory."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import threading

_lock = threading.RLock()


def popen(args, **kwargs):
    if not (sys.platform=='win32' and getattr(sys,'frozen',False)):
        return subprocess.Popen(args,**kwargs)
    with _lock:
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        bundle = str(Path(sys._MEIPASS).resolve())
        env = dict(kwargs.pop('env',os.environ))
        env['PATH'] = os.pathsep.join(p for p in env.get('PATH','').split(os.pathsep)
                                    if p and not Path(p).resolve().is_relative_to(Path(bundle)))
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return subprocess.Popen(args,env=env,**kwargs)
        finally:
            if not kernel.SetDllDirectoryW(bundle):
                raise ctypes.WinError(ctypes.get_last_error())


def run(args, *, capture_output=False, timeout=None, check=False, **kwargs):
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    with popen(args,**kwargs) as process:
        try:
            stdout,stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        result = subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
        if check:
            result.check_returncode()
        return result
