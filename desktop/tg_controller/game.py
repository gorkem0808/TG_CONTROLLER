from __future__ import annotations

import ctypes
import os
import shlex
import subprocess
import threading
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path

from .config import AppConfig


TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


def _windows_process_names() -> set[str]:
    """Return running executable names without external packages."""
    if os.name != "nt":
        return set()

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE

    process_first = kernel32.Process32FirstW
    process_first.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    process_first.restype = wintypes.BOOL

    process_next = kernel32.Process32NextW
    process_next.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    process_next.restype = wintypes.BOOL

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    snapshot = create_snapshot(TH32CS_SNAPPROCESS, 0)
    invalid_handle = ctypes.c_void_p(-1).value

    if snapshot == invalid_handle:
        return set()

    names: set[str] = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    try:
        if process_first(snapshot, ctypes.byref(entry)):
            while True:
                name = str(entry.szExeFile).strip().casefold()
                if name:
                    names.add(name)

                if not process_next(snapshot, ctypes.byref(entry)):
                    break
    finally:
        close_handle(snapshot)

    return names


def _portable_process_names() -> set[str]:
    """Best-effort fallback used only outside Windows development tests."""
    if os.name == "nt":
        return _windows_process_names()

    try:
        result = subprocess.run(
            ["ps", "-A", "-o", "comm="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return set()

    return {
        Path(line.strip()).name.casefold()
        for line in result.stdout.splitlines()
        if line.strip()
    }


class GameManager:
    def __init__(self, callback: Callable[[dict], None]) -> None:
        self.callback = callback
        self.process: subprocess.Popen | None = None
        self.countdown_cancel_event = threading.Event()
        self.stop_requested_event = threading.Event()
        self.monitor_thread: threading.Thread | None = None
        self.config: AppConfig | None = None
        self.send_macro: Callable[[], bool] | None = None

    def is_game_running(self, executable: str) -> bool:
        if self.process is not None and self.process.poll() is None:
            return True

        expected_name = Path(executable).name.casefold()
        if not expected_name:
            return False

        return expected_name in _portable_process_names()

    def launch(
        self,
        cfg: AppConfig,
        send_macro: Callable[[], bool],
    ) -> bool:
        self.config = cfg
        self.send_macro = send_macro

        path = Path(cfg.game_path)
        if not path.exists():
            self.callback(
                {
                    "type": "game_error",
                    "message": f"Oyun bulunamadı: {path}",
                }
            )
            return False

        if self.is_game_running(str(path)):
            self.callback(
                {
                    "type": "game_already_running",
                    "path": str(path),
                }
            )
            if cfg.macro_enabled:
                self.start_countdown(
                    cfg.macro_delay_seconds,
                    send_macro,
                )
            return False

        args = [str(path)]
        if cfg.game_arguments.strip():
            args.extend(
                shlex.split(
                    cfg.game_arguments,
                    posix=False,
                )
            )

        working_directory = (
            cfg.working_directory
            or str(path.parent)
        )

        try:
            self.process = subprocess.Popen(
                args,
                cwd=working_directory,
            )
        except OSError as exc:
            self.callback(
                {
                    "type": "game_error",
                    "message": str(exc),
                }
            )
            return False

        self.countdown_cancel_event.clear()
        self.stop_requested_event.clear()

        self.callback(
            {
                "type": "game_started",
                "pid": self.process.pid,
            }
        )

        self.monitor_thread = threading.Thread(
            target=self._monitor,
            daemon=True,
        )
        self.monitor_thread.start()

        if cfg.macro_enabled:
            self.start_countdown(
                cfg.macro_delay_seconds,
                send_macro,
            )

        return True

    def start_countdown(
        self,
        seconds: int,
        send_macro: Callable[[], bool],
    ) -> None:
        self.countdown_cancel_event.clear()

        def worker() -> None:
            remaining = max(
                0,
                min(999, int(seconds)),
            )

            while (
                remaining > 0
                and not self.countdown_cancel_event.is_set()
            ):
                self.callback(
                    {
                        "type": "macro_countdown",
                        "remaining": remaining,
                    }
                )

                if not self._game_still_available():
                    self.callback(
                        {
                            "type": "macro_cancelled",
                            "reason": "Oyun kapandı",
                        }
                    )
                    return

                if self.countdown_cancel_event.wait(1.0):
                    return

                remaining -= 1

            if self.countdown_cancel_event.is_set():
                self.callback(
                    {
                        "type": "macro_cancelled",
                        "reason": "Kullanıcı iptal etti",
                    }
                )
                return

            self.callback(
                {
                    "type": "macro_countdown",
                    "remaining": 0,
                }
            )

            if send_macro():
                self.callback(
                    {
                        "type": "macro_requested",
                    }
                )
            else:
                self.callback(
                    {
                        "type": "macro_error",
                        "message": "Controller bağlı değil",
                    }
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def cancel_countdown(self) -> None:
        self.countdown_cancel_event.set()

    def cancel_countdown_for_manual_macro(self) -> None:
        """Cancel the automatic timer when GP9/GP2 starts the fixed macro."""
        self.countdown_cancel_event.set()

    def stop_game(self) -> None:
        self.countdown_cancel_event.set()
        self.stop_requested_event.set()

        process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except OSError:
                    pass

        self.process = None
        self.callback({"type": "game_stopped"})

    def _game_still_available(self) -> bool:
        if self.process is not None:
            return self.process.poll() is None

        if self.config:
            return self.is_game_running(
                self.config.game_path
            )

        return False

    def _monitor(self) -> None:
        process = self.process
        if process is None:
            return

        return_code = process.wait()
        self.callback(
            {
                "type": "game_exited",
                "return_code": return_code,
            }
        )
        self.process = None

        cfg = self.config
        if (
            cfg
            and cfg.auto_restart_game
            and not self.stop_requested_event.is_set()
        ):
            self.callback(
                {
                    "type": "restart_wait",
                    "seconds": cfg.restart_delay_seconds,
                }
            )

            if (
                not self.stop_requested_event.wait(
                    cfg.restart_delay_seconds
                )
                and self.send_macro
            ):
                self.launch(
                    cfg,
                    self.send_macro,
                )
