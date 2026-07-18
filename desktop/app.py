from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tkinter as tk
from tkinter import messagebox

from tg_controller.single_instance import SingleInstance
from tg_controller.ui import APP_TITLE, ManagerApp


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Programı sistem tepsisinde/gizli başlat.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Paketlenmiş modülleri kontrol edip pencere açmadan çık.",
    )
    return parser.parse_args(argv)


def notify_existing_instance() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                "TG_CONTROLLER_PRO zaten çalışıyor. Saat yanındaki sistem tepsisi simgesinden açabilirsiniz.",
                APP_TITLE,
                0x40,
            )
            return
        except Exception:
            pass
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(APP_TITLE, "TG_CONTROLLER_PRO zaten çalışıyor.")
    root.destroy()


def main() -> int:
    args = parse_args(sys.argv[1:])
    if args.self_test:
        # ui importu dosyanın başında gerçekleşir. Buraya ulaşıldıysa
        # paketlenmiş zorunlu modüller başarıyla yüklenmiştir.
        return 0

    instance = SingleInstance()
    if instance.already_running:
        notify_existing_instance()
        instance.close()
        return 0

    root = tk.Tk()
    try:
        ManagerApp(root, start_minimized=args.minimized)
        root.mainloop()
    finally:
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
