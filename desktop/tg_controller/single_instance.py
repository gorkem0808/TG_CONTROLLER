from __future__ import annotations

import ctypes
import os


class SingleInstance:
    def __init__(self, name: str = "Local\\TG_CONTROLLER_PRO_V4_SINGLE_INSTANCE") -> None:
        self.handle = None
        self.already_running = False
        if os.name == "nt":
            self.handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
            self.already_running = ctypes.windll.kernel32.GetLastError() == 183

    def close(self) -> None:
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
