from __future__ import annotations

import threading
from collections.abc import Callable


class TrayController:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_toggle: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.on_show = on_show
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self.icon = None

    def start(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return

        image = Image.new("RGB", (64, 64), "#182330")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), outline="#2f8cff", width=5)
        draw.line((32, 14, 32, 50), fill="white", width=4)
        draw.line((14, 32, 50, 32), fill="white", width=4)

        menu = pystray.Menu(
            pystray.MenuItem("Programı Göster", lambda _icon, _item: self.on_show()),
            pystray.MenuItem("F8 — Silahları Aç/Kapat", lambda _icon, _item: self.on_toggle()),
            pystray.MenuItem("Tamamen Kapat", lambda _icon, _item: self.on_quit()),
        )
        self.icon = pystray.Icon("TG_CONTROLLER_PRO", image, "TG_CONTROLLER_PRO V4.1", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
