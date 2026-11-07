"""Start OS utilities without inheriting PyInstaller's DLL directory."""
import ctypes
import ntpath
import os
import subprocess
import sys
import threading

_lock = threading.RLock()


def child_environment(environment,bundle):
    """Filter bundle paths lexically; never traverse unrelated PATH symlinks/mounts."""
    result=dict(environment)
    bundled=ntpath.normcase(ntpath.normpath(os.fspath(bundle)))
    paths=[]
    for entry in result.get('PATH','').split(os.pathsep):
        if not entry:
            continue
        normalized=ntpath.normcase(ntpath.normpath(entry.strip('"')))
        try:
            inside=ntpath.commonpath([normalized,bundled])==bundled
        except ValueError:
            inside=False
        if not inside:
            paths.append(entry)
    result['PATH']=os.pathsep.join(paths)
    return result


def popen(args, **kwargs):
    if not (sys.platform=='win32' and getattr(sys,'frozen',False)):
        return subprocess.Popen(args,**kwargs)
    with _lock:
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        bundle = os.fspath(sys._MEIPASS)
        env = child_environment(kwargs.pop('env',os.environ),bundle)
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
