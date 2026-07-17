from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import serial
from serial.tools import list_ports


APP_TITLE = "TG_CONTROLLER_MANAGER V005"
BAUD_RATE = 115200

BG = "#111821"
PANEL = "#1a2430"
PANEL_2 = "#22303e"
TEXT = "#f3f6f8"
MUTED = "#9fb0c0"
ACCENT = "#2e8cff"
OK = "#22c55e"
BAD = "#ef4444"


@dataclass
class DeviceIdentity:
    key: str
    name: str
    expected_token: str


IDENTITIES = {
    "controller": DeviceIdentity("controller", "Controller", "NAME=TG_CONTROLLER"),
    "p1": DeviceIdentity("p1", "Player 1", "NAME=TG_GUN_P1"),
    "p2": DeviceIdentity("p2", "Player 2", "NAME=TG_GUN_P2"),
}


class SerialSession:
    def __init__(
        self,
        key: str,
        event_queue: queue.Queue[tuple[str, str, str]],
    ) -> None:
        self.key = key
        self.event_queue = event_queue
        self.port: serial.Serial | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    @property
    def connected(self) -> bool:
        return self.port is not None and self.port.is_open

    def connect(self, device: str) -> None:
        self.disconnect()
        self.port = serial.Serial(device, BAUD_RATE, timeout=0.2)
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()

    def disconnect(self) -> None:
        self.stop_event.set()
        port = self.port
        self.port = None
        if port:
            try:
                port.close()
            except serial.SerialException:
                pass

    def send(self, command: str) -> None:
        if not self.connected or self.port is None:
            raise serial.SerialException("Cihaz bağlı değil.")
        self.port.write((command + "\n").encode("ascii"))
        self.port.flush()

    def _reader_loop(self) -> None:
        while not self.stop_event.is_set():
            port = self.port
            if port is None:
                return
            try:
                raw = port.readline()
            except serial.SerialException as exc:
                self.event_queue.put((self.key, "error", str(exc)))
                return
            if raw:
                line = raw.decode("utf-8", errors="replace").strip()
                self.event_queue.put((self.key, "line", line))


class TGControllerManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x720")
        self.minsize(1000, 650)
        self.configure(bg=BG)

        self.events: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self.sessions = {
            key: SerialSession(key, self.events) for key in IDENTITIES
        }

        self.port_vars = {key: tk.StringVar() for key in IDENTITIES}
        self.status_vars = {
            key: tk.StringVar(value="BAĞLI DEĞİL") for key in IDENTITIES
        }
        self.version_vars = {
            key: tk.StringVar(value="-") for key in IDENTITIES
        }

        self.controller_buttons = {
            "Coin": tk.StringVar(value="PASİF"),
            "P1 Start": tk.StringVar(value="PASİF"),
            "P1 Trigger": tk.StringVar(value="PASİF"),
            "P1 Bomb": tk.StringVar(value="PASİF"),
            "P2 Start": tk.StringVar(value="PASİF"),
            "P2 Trigger": tk.StringVar(value="PASİF"),
            "P2 Bomb": tk.StringVar(value="PASİF"),
        }

        self.gun_values = {
            "p1": {
                "x": tk.StringVar(value="0"),
                "y": tk.StringVar(value="0"),
                "motion": tk.StringVar(value="AKTİF"),
            },
            "p2": {
                "x": tk.StringVar(value="0"),
                "y": tk.StringVar(value="0"),
                "motion": tk.StringVar(value="AKTİF"),
            },
        }

        self.status_bar_var = tk.StringVar(value="HAZIR")
        self.page_frames: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self.port_combos: dict[str, ttk.Combobox] = {}
        self.status_dots: dict[str, tuple[tk.Canvas, int]] = {}
        self.button_labels: dict[str, tk.Label] = {}

        self._build_style()
        self._build_ui()
        self.refresh_ports()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=PANEL_2,
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=PANEL, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="TG_CONTROLLER_MANAGER",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 17, "bold"),
        ).pack(side="left", padx=18)

        tk.Label(
            header,
            text="V005",
            bg=PANEL,
            fg=ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="right", padx=18)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=PANEL, width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self._add_nav(sidebar, "dashboard", "Dashboard")
        self._add_nav(sidebar, "controller", "Controller")
        self._add_nav(sidebar, "p1", "Player 1")
        self._add_nav(sidebar, "p2", "Player 2")
        self._add_nav(sidebar, "firmware", "Firmware")
        self._add_nav(sidebar, "logs", "Logs")

        status = tk.Frame(self, bg=PANEL, height=34)
        status.pack(fill="x")
        status.pack_propagate(False)
        tk.Label(
            status,
            textvariable=self.status_bar_var,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="both", padx=14)

        self._create_dashboard()
        self._create_controller()
        self._create_gun_page("p1", "Player 1")
        self._create_gun_page("p2", "Player 2")
        self._create_firmware()
        self._create_logs()
        self.show_page("dashboard")

    def _add_nav(self, parent: tk.Frame, key: str, text: str) -> None:
        button = tk.Button(
            parent,
            text=text,
            command=lambda selected=key: self.show_page(selected),
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL_2,
            activeforeground=TEXT,
            bd=0,
            anchor="w",
            padx=22,
            pady=15,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        button.pack(fill="x")
        self.nav_buttons[key] = button

    def _new_page(self, key: str) -> tk.Frame:
        page = tk.Frame(self.content, bg=BG)
        self.page_frames[key] = page
        return page

    def show_page(self, key: str) -> None:
        for page in self.page_frames.values():
            page.pack_forget()
        for nav_key, button in self.nav_buttons.items():
            button.configure(bg=PANEL_2 if nav_key == key else PANEL)
        self.page_frames[key].pack(fill="both", expand=True)

    def _title(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=24, pady=(20, 12))

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        frame = tk.Frame(
            parent,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=PANEL_2,
        )
        tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))
        return frame

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        width: int = 15,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=ACCENT,
            fg="white",
            activebackground="#1d6fd1",
            activeforeground="white",
            bd=0,
            padx=10,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

    def _create_dashboard(self) -> None:
        page = self._new_page("dashboard")
        self._title(page, "Dashboard")

        toolbar = tk.Frame(page, bg=BG)
        toolbar.pack(fill="x", padx=24, pady=(0, 10))
        self._button(toolbar, "Portları Yenile", self.refresh_ports).pack(side="left", padx=4)
        self._button(toolbar, "Üçünü Bağla", self.connect_all).pack(side="left", padx=4)
        self._button(toolbar, "Tümünü Kes", self.disconnect_all).pack(side="left", padx=4)

        for key in ("controller", "p1", "p2"):
            self._device_connection_card(page, key)

    def _device_connection_card(self, parent: tk.Widget, key: str) -> None:
        ident = IDENTITIES[key]
        card = self._card(parent, ident.name)
        card.pack(fill="x", padx=24, pady=(0, 10))

        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", padx=16, pady=(0, 14))

        canvas = tk.Canvas(row, width=22, height=22, bg=PANEL, highlightthickness=0)
        canvas.pack(side="left", padx=(0, 8))
        dot = canvas.create_oval(3, 3, 19, 19, fill=BAD, outline="")
        self.status_dots[key] = (canvas, dot)

        tk.Label(
            row,
            textvariable=self.status_vars[key],
            bg=PANEL,
            fg=TEXT,
            width=13,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        combo = ttk.Combobox(
            row,
            textvariable=self.port_vars[key],
            state="readonly",
            style="Dark.TCombobox",
            width=34,
        )
        combo.pack(side="left", padx=4)
        self.port_combos[key] = combo

        self._button(
            row,
            "Bağlan / Kes",
            lambda selected=key: self.toggle_device(selected),
            width=13,
        ).pack(side="left", padx=5)

        tk.Label(row, text="Firmware:", bg=PANEL, fg=MUTED).pack(side="left", padx=(18, 4))
        tk.Label(
            row,
            textvariable=self.version_vars[key],
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

    def _create_controller(self) -> None:
        page = self._new_page("controller")
        self._title(page, "Controller")

        card = self._card(page, "Canlı Tuş Durumu")
        card.pack(fill="x", padx=24, pady=(0, 12))

        grid = tk.Frame(card, bg=PANEL)
        grid.pack(fill="x", padx=16, pady=(0, 16))

        for index, (name, variable) in enumerate(self.controller_buttons.items()):
            item = tk.Frame(grid, bg=PANEL_2, width=165, height=78)
            item.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="nsew")
            item.grid_propagate(False)

            tk.Label(
                item,
                text=name,
                bg=PANEL_2,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
            ).pack(pady=(12, 4))

            label = tk.Label(
                item,
                textvariable=variable,
                bg=PANEL_2,
                fg=MUTED,
                font=("Segoe UI", 9, "bold"),
            )
            label.pack()
            self.button_labels[name] = label

        for col in range(4):
            grid.columnconfigure(col, weight=1)

        relay = self._card(page, "Röle Testi")
        relay.pack(fill="x", padx=24, pady=(0, 12))
        inner = tk.Frame(relay, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=(0, 16))
        self._button(
            inner,
            "Röle 1 Test",
            lambda: self.send_command("controller", "RELAY 1 PULSE"),
        ).pack(side="left", padx=5)
        self._button(
            inner,
            "Röle 2 Test",
            lambda: self.send_command("controller", "RELAY 2 PULSE"),
        ).pack(side="left", padx=5)

    def _create_gun_page(self, key: str, title: str) -> None:
        page = self._new_page(key)
        self._title(page, title)

        card = self._card(page, "Canlı Potansiyometre")
        card.pack(fill="x", padx=24, pady=(0, 12))

        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=(0, 16))

        values = self.gun_values[key]
        self._info_row(inner, 0, "X ADC", values["x"])
        self._info_row(inner, 1, "Y ADC", values["y"])
        self._info_row(inner, 2, "Hareket", values["motion"])

        actions = tk.Frame(card, bg=PANEL)
        actions.pack(fill="x", padx=16, pady=(0, 16))
        self._button(
            actions,
            "Hareket Aç",
            lambda selected=key: self.send_command(selected, "MOTION ON"),
        ).pack(side="left", padx=4)
        self._button(
            actions,
            "Hareket Kapat",
            lambda selected=key: self.send_command(selected, "MOTION OFF"),
        ).pack(side="left", padx=4)
        self._button(
            actions,
            "Durumu Oku",
            lambda selected=key: self.send_command(selected, "STATUS"),
        ).pack(side="left", padx=4)

    def _create_firmware(self) -> None:
        page = self._new_page("firmware")
        self._title(page, "Firmware")

        self.firmware_paths = {
            key: tk.StringVar(value="Dosya seçilmedi") for key in IDENTITIES
        }

        expected = {
            "controller": "TG_CONTROLLER_V005.uf2",
            "p1": "TG_GUN_P1_V005.uf2",
            "p2": "TG_GUN_P2_V005.uf2",
        }

        for key in ("controller", "p1", "p2"):
            card = self._card(page, IDENTITIES[key].name)
            card.pack(fill="x", padx=24, pady=(0, 10))
            inner = tk.Frame(card, bg=PANEL)
            inner.pack(fill="x", padx=16, pady=(0, 14))
            tk.Label(
                inner,
                text=f"Beklenen dosya: {expected[key]}",
                bg=PANEL,
                fg=MUTED,
            ).pack(anchor="w", pady=(0, 6))
            tk.Label(
                inner,
                textvariable=self.firmware_paths[key],
                bg=PANEL_2,
                fg=TEXT,
                anchor="w",
                padx=8,
                pady=7,
            ).pack(fill="x", pady=(0, 7))
            self._button(
                inner,
                "UF2 Seç",
                lambda selected=key: self.choose_uf2(selected),
                width=12,
            ).pack(anchor="w")

    def _create_logs(self) -> None:
        page = self._new_page("logs")
        self._title(page, "Logs")

        card = self._card(page, "Canlı Seri Haberleşme")
        card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        frame = tk.Frame(card, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log = tk.Text(
            frame,
            bg="#0d131b",
            fg=TEXT,
            insertbackground=TEXT,
            wrap="word",
            state="disabled",
            bd=0,
            font=("Consolas", 10),
        )
        self.log.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

    def _info_row(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        tk.Label(
            parent,
            text=label,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=5)

        tk.Label(
            parent,
            textvariable=variable,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=1, sticky="w", pady=5)

    def refresh_ports(self) -> None:
        values = [
            f"{port.device} — {port.description}"
            for port in list_ports.comports()
        ]
        for key, combo in self.port_combos.items():
            combo["values"] = values
            if values and not self.port_vars[key].get():
                combo.current(0)
        self.status_bar_var.set("PORT LİSTESİ YENİLENDİ")

    def toggle_device(self, key: str) -> None:
        if self.sessions[key].connected:
            self.disconnect_device(key)
        else:
            self.connect_device(key)

    def connect_device(self, key: str) -> None:
        selection = self.port_vars[key].get()
        if not selection:
            messagebox.showwarning(APP_TITLE, f"{IDENTITIES[key].name} için port seç.")
            return

        device = selection.split(" — ", 1)[0]
        try:
            self.sessions[key].connect(device)
        except serial.SerialException as exc:
            messagebox.showerror(APP_TITLE, f"{device} açılamadı:\n{exc}")
            return

        self.status_vars[key].set("BAĞLANIYOR")
        self._set_dot(key, WARN)
        self._append_log(key, f"Bağlandı: {device}")
        self.send_command(key, "PING", warn=False)
        self.send_command(key, "INFO", warn=False)

    def disconnect_device(self, key: str) -> None:
        self.sessions[key].disconnect()
        self.status_vars[key].set("BAĞLI DEĞİL")
        self.version_vars[key].set("-")
        self._set_dot(key, BAD)
        self._append_log(key, "Bağlantı kesildi.")

    def connect_all(self) -> None:
        selected_ports: set[str] = set()
        for key in ("controller", "p1", "p2"):
            selection = self.port_vars[key].get()
            device = selection.split(" — ", 1)[0] if selection else ""
            if not device or device in selected_ports:
                continue
            selected_ports.add(device)
            self.connect_device(key)

    def disconnect_all(self) -> None:
        for key in self.sessions:
            self.disconnect_device(key)

    def send_command(self, key: str, command: str, warn: bool = True) -> None:
        try:
            self.sessions[key].send(command)
            self._append_log(key, f"> {command}")
        except serial.SerialException as exc:
            if warn:
                messagebox.showwarning(APP_TITLE, f"{IDENTITIES[key].name}: {exc}")

    def _drain_events(self) -> None:
        while True:
            try:
                key, event_type, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if event_type == "line":
                self._append_log(key, payload)
                self._process_line(key, payload)
            else:
                self._append_log(key, f"HATA: {payload}")
                self.disconnect_device(key)

        self.after(100, self._drain_events)

    def _process_line(self, key: str, line: str) -> None:
        if line.startswith("PONG"):
            self.status_vars[key].set("BAĞLI")
            self._set_dot(key, OK)
        elif line.startswith("INFO"):
            expected = IDENTITIES[key].expected_token
            if expected not in line:
                self.status_vars[key].set("YANLIŞ CİHAZ")
                self._set_dot(key, BAD)
                return

            values = self._parse_values(line)
            self.version_vars[key].set(values.get("VERSION", "-"))
            self.status_vars[key].set("BAĞLI")
            self._set_dot(key, OK)
        elif key == "controller" and line.startswith("STATUS"):
            values = self._parse_values(line)
            mapping = {
                "Coin": "C",
                "P1 Start": "S1",
                "P1 Trigger": "T1",
                "P1 Bomb": "B1",
                "P2 Start": "S2",
                "P2 Trigger": "T2",
                "P2 Bomb": "B2",
            }
            for name, code in mapping.items():
                active = values.get(code) == "1"
                self.controller_buttons[name].set("AKTİF" if active else "PASİF")
                self.button_labels[name].configure(fg=OK if active else MUTED)
        elif key in ("p1", "p2") and line.startswith("GUNSTATUS"):
            values = self._parse_values(line)
            self.gun_values[key]["x"].set(values.get("X", "0"))
            self.gun_values[key]["y"].set(values.get("Y", "0"))
            self.gun_values[key]["motion"].set(
                "AKTİF" if values.get("MOTION") == "1" else "PASİF"
            )

    @staticmethod
    def _parse_values(line: str) -> dict[str, str]:
        output: dict[str, str] = {}
        for token in line.split()[1:]:
            if "=" in token:
                name, value = token.split("=", 1)
                output[name] = value
        return output

    def _set_dot(self, key: str, color: str) -> None:
        canvas, dot = self.status_dots[key]
        canvas.itemconfigure(dot, fill=color)

    def choose_uf2(self, key: str) -> None:
        path = filedialog.askopenfilename(
            title=f"{IDENTITIES[key].name} UF2 Dosyası Seç",
            filetypes=[("UF2 Firmware", "*.uf2"), ("Tüm Dosyalar", "*.*")],
        )
        if path:
            self.firmware_paths[key].set(path)

    def _append_log(self, key: str, text: str) -> None:
        if not hasattr(self, "log"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert(
            "end",
            f"{timestamp}  [{IDENTITIES[key].name}] {text}\n",
        )
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_close(self) -> None:
        self.disconnect_all()
        self.destroy()


if __name__ == "__main__":
    TGControllerManager().mainloop()
