from __future__ import annotations

import ctypes
import os


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


class SingleInstance:
    def __init__(
        self,
        name: str = "Local\\TG_CONTROLLER_PRO_V4_SINGLE_INSTANCE",
        show_event_name: str = "Local\\TG_CONTROLLER_PRO_SHOW_WINDOW",
    ) -> None:
        self.handle = None
        self.show_event_handle = None
        self.already_running = False

        if os.name != "nt":
            return

        kernel32 = ctypes.windll.kernel32

        self.handle = kernel32.CreateMutexW(
            None,
            False,
            name,
        )
        self.already_running = (
            kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        )

        self.show_event_handle = kernel32.CreateEventW(
            None,
            True,
            False,
            show_event_name,
        )

    def signal_show_request(self) -> None:
        if os.name == "nt" and self.show_event_handle:
            ctypes.windll.kernel32.SetEvent(
                self.show_event_handle
            )

    def consume_show_request(self) -> bool:
        if os.name != "nt" or not self.show_event_handle:
            return False

        result = ctypes.windll.kernel32.WaitForSingleObject(
            self.show_event_handle,
            0,
        )

        if result == WAIT_OBJECT_0:
            ctypes.windll.kernel32.ResetEvent(
                self.show_event_handle
            )
            return True

        return False

    def close(self) -> None:
        if os.name != "nt":
            return

        kernel32 = ctypes.windll.kernel32

        if self.show_event_handle:
            kernel32.CloseHandle(
                self.show_event_handle
            )
            self.show_event_handle = None

        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None
