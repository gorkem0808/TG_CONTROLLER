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
        self.thread: threading.Thread | None = None
        self.ready_event = threading.Event()
        self.failed_event = threading.Event()
        self.last_error = ""
        self.started = False

    def start(self, timeout_seconds: float = 4.0) -> bool:
        if self.started:
            return True

        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as exc:
            self.last_error = f"Tepsi modülü yüklenemedi: {exc}"
            self.failed_event.set()
            return False

        image = Image.new("RGBA", (64, 64), (24, 35, 48, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (7, 7, 57, 57),
            outline=(47, 140, 255, 255),
            width=5,
        )
        draw.line(
            (32, 14, 32, 50),
            fill=(255, 255, 255, 255),
            width=4,
        )
        draw.line(
            (14, 32, 50, 32),
            fill=(255, 255, 255, 255),
            width=4,
        )

        menu = pystray.Menu(
            pystray.MenuItem(
                "Programı Göster",
                lambda _icon, _item: self.on_show(),
                default=True,
            ),
            pystray.MenuItem(
                "F8 — Silahları Aç/Kapat",
                lambda _icon, _item: self.on_toggle(),
            ),
            pystray.MenuItem(
                "Tamamen Kapat",
                lambda _icon, _item: self.on_quit(),
            ),
        )

        self.icon = pystray.Icon(
            "TG_CONTROLLER_PRO",
            image,
            "TG_CONTROLLER_PRO V4.2",
            menu,
        )

        def setup(icon) -> None:
            try:
                icon.visible = True
                self.started = True
                self.ready_event.set()
            except Exception as exc:
                self.last_error = f"Tepsi simgesi görünür yapılamadı: {exc}"
                self.failed_event.set()
                self.ready_event.set()

        def runner() -> None:
            try:
                self.icon.run(setup=setup)
            except Exception as exc:
                self.last_error = f"Tepsi servisi başlatılamadı: {exc}"
                self.failed_event.set()
                self.ready_event.set()
                self.started = False

        self.ready_event.clear()
        self.failed_event.clear()
        self.thread = threading.Thread(
            target=runner,
            name="TGControllerTray",
            daemon=True,
        )
        self.thread.start()

        self.ready_event.wait(timeout_seconds)

        if self.failed_event.is_set() or not self.started:
            if not self.last_error:
                self.last_error = (
                    "Sistem tepsisi belirtilen sürede başlatılamadı."
                )
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

        self.icon = None
        self.started = False
