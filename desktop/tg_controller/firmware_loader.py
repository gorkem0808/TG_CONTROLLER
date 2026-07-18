from __future__ import annotations

import os
import shutil
import string
import threading
import time
from collections.abc import Callable
from pathlib import Path


class FirmwareLoader:
    def __init__(self, callback: Callable[[dict], None]) -> None:
        self.callback = callback

    @staticmethod
    def find_rpi_rp2_drive() -> Path | None:
        if os.name != "nt":
            return None
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            try:
                if (root / "INFO_UF2.TXT").exists():
                    return root
            except OSError:
                continue
        return None

    def update(
        self,
        role: str,
        uf2_path: str,
        request_bootsel: Callable[[str], bool],
    ) -> None:
        def worker() -> None:
            source = Path(uf2_path)
            if not source.exists() or source.suffix.lower() != ".uf2":
                self.callback({"type": "firmware_error", "role": role, "message": "Geçerli UF2 seçilmedi."})
                return
            self.callback({"type": "firmware_status", "role": role, "message": "BOOTSEL isteniyor"})
            if not request_bootsel(role):
                self.callback({
                    "type": "firmware_error",
                    "role": role,
                    "message": "İlgili Pico bağlı değil; BOOTSEL düğmesiyle elle takın.",
                })
                return
            deadline = time.monotonic() + 20.0
            drive = None
            while time.monotonic() < deadline:
                drive = self.find_rpi_rp2_drive()
                if drive:
                    break
                time.sleep(0.4)
            if drive is None:
                self.callback(
                    {
                        "type": "firmware_error",
                        "role": role,
                        "message": "RPI-RP2 sürücüsü bulunamadı. BOOTSEL ile elle takıp tekrar deneyin.",
                    }
                )
                return
            try:
                target = drive / source.name
                shutil.copy2(source, target)
            except OSError as exc:
                self.callback({"type": "firmware_error", "role": role, "message": str(exc)})
                return
            self.callback({"type": "firmware_done", "role": role, "file": source.name})

        threading.Thread(target=worker, daemon=True).start()
