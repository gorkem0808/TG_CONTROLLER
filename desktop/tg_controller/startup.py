from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "TG_CONTROLLER_PRO_V4"


def executable_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --minimized'
    app = Path(__file__).resolve().parents[1] / "app.py"
    return f'"{sys.executable}" "{app}" --minimized'


def set_autostart(enabled: bool) -> None:
    if os.name != "nt":
        return
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, executable_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def is_autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_QUERY_VALUE) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False
