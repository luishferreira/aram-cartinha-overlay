"""Installed resources and per-user state have separate lifetimes."""
import os
from pathlib import Path
import sys


def app_root():
    if getattr(sys,'frozen',False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def local_root(root=None):
    root = Path(root) if root is not None else app_root()
    override = os.environ.get('ARAM_CARTINHA_USER_DIR')
    if override:
        folder = Path(override)
        if not folder.is_absolute():
            raise ValueError('ARAM_CARTINHA_USER_DIR must be an absolute path')
        return folder
    if not getattr(sys,'frozen',False):
        return root/'data/local'
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        raise RuntimeError('Windows LOCALAPPDATA is unavailable')
    return Path(local)/'AramCartinhaOverlay'
