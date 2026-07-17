from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import serial
from serial.tools import list_ports


APP_TITLE = "TG_CONTROLLER_MANAGER V003"
BAUD_RATE = 115200

BG = "#121821"
PANEL = "#1a2430"
PANEL_2 = "#202c3a"
TEXT = "#f2f5f7"
MUTED = "#9fb0c0"
ACCENT = "#2e8cff"
OK = "#22c55e"
BAD = "#ef4444"
WARN = "#f59e0b"


class TGControllerManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("980x640")
        self.minsize(900, 600)
        self.configure(bg=BG)

        self.serial_port: serial.Serial | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.rx_queue: queue.Queue[str] = queue.Queue()

        self.port_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="BAĞLI DEĞİL")
        self.firmware_var = tk.StringVar(value="-")
        self.com_var = tk.StringVar(value="-")
        self.usb_var = tk.StringVar(value="HID + CDC")
        self.status_bar_var = tk.StringVar(value="HAZIR")

        self.button_state_vars = {
            "Coin": tk.StringVar(value="PASİF"),
            "P1 Start": tk.StringVar(value="PASİF"),
            "P1 Trigger": tk.StringVar(value="PASİF"),
            "P1 Bomb": tk.StringVar(value="PASİF"),
            "P2 Start": tk.StringVar(value="PASİF"),
            "P2 Trigger": tk.StringVar(value="PASİF"),
            "P2 Bomb": tk.StringVar(value="PASİF"),
        }

        self.current_page = "dashboard"
        self.page_frames: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}

        self._build_styles()
        self._build_ui()
        self.refresh_ports()
        self.after(100, self._drain_rx_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_styles(self) -> None:
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
            text="V003",
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

        self._add_nav_button(sidebar, "dashboard", "Dashboard")
        self._add_nav_button(sidebar, "controller", "Controller")
        self._add_nav_button(sidebar, "firmware", "Firmware")
        self._add_nav_button(sidebar, "settings", "Settings")
        self._add_nav_button(sidebar, "logs", "Logs")

        status_bar = tk.Frame(self, bg=PANEL, height=34)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        tk.Label(
            status_bar,
            textvariable=self.status_bar_var,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="both", padx=14)

        self._create_dashboard_page()
        self._create_controller_page()
        self._create_firmware_page()
        self._create_settings_page()
        self._create_logs_page()

        self.show_page("dashboard")

    def _add_nav_button(self, parent: tk.Frame, key: str, text: str) -> None:
        button = tk.Button(
            parent,
            text=text,
            command=lambda k=key: self.show_page(k),
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL_2,
            activeforeground=TEXT,
            bd=0,
            relief="flat",
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
        self.current_page = key

    def _section_title(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=24, pady=(20, 12))

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=1, highlightbackground=PANEL_2)
        tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))
        return frame

    def _create_dashboard_page(self) -> None:
        page = self._new_page("dashboard")
        self._section_title(page, "Dashboard")

        connect_card = self._card(page, "Controller Bağlantısı")
        connect_card.pack(fill="x", padx=24, pady=(0, 12))

        top = tk.Frame(connect_card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(0, 16))

        self.connection_indicator = tk.Canvas(top, width=22, height=22, bg=PANEL, highlightthickness=0)
        self.connection_indicator.pack(side="left", padx=(0, 10))
        self.connection_dot = self.connection_indicator.create_oval(3, 3, 19, 19, fill=BAD, outline="")

        tk.Label(
            top,
            textvariable=self.connection_var,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        connection_controls = tk.Frame(connect_card, bg=PANEL)
        connection_controls.pack(fill="x", padx=16, pady=(0, 14))

        self.port_combo = ttk.Combobox(
            connection_controls,
            textvariable=self.port_var,
            state="readonly",
            style="Dark.TCombobox",
            width=36,
        )
        self.port_combo.pack(side="left", padx=(0, 8))

        self._button(connection_controls, "Yenile", self.refresh_ports, width=10).pack(side="left", padx=4)
        self.connect_button = self._button(connection_controls, "Bağlan", self.toggle_connection, width=14)
        self.connect_button.pack(side="left", padx=4)

        info_card = self._card(page, "Cihaz Bilgisi")
        info_card.pack(fill="x", padx=24, pady=(0, 12))

        info_grid = tk.Frame(info_card, bg=PANEL)
        info_grid.pack(fill="x", padx=16, pady=(0, 16))

        self._info_row(info_grid, 0, "Firmware", self.firmware_var)
        self._info_row(info_grid, 1, "COM Port", self.com_var)
        self._info_row(info_grid, 2, "USB", self.usb_var)

        quick_card = self._card(page, "Hızlı İşlemler")
        quick_card.pack(fill="x", padx=24, pady=(0, 12))
        quick_buttons = tk.Frame(quick_card, bg=PANEL)
        quick_buttons.pack(fill="x", padx=16, pady=(0, 16))

        self._button(quick_buttons, "Cihaz Bilgisi", lambda: self.send_command("INFO")).pack(side="left", padx=4)
        self._button(quick_buttons, "Durumu Oku", lambda: self.send_command("STATUS")).pack(side="left", padx=4)
        self._button(quick_buttons, "Röle 1 Test", lambda: self.send_command("RELAY 1 PULSE")).pack(side="left", padx=4)
        self._button(quick_buttons, "Röle 2 Test", lambda: self.send_command("RELAY 2 PULSE")).pack(side="left", padx=4)

    def _create_controller_page(self) -> None:
        page = self._new_page("controller")
        self._section_title(page, "Controller Test")

        button_card = self._card(page, "Canlı Tuş Durumu")
        button_card.pack(fill="x", padx=24, pady=(0, 12))

        grid = tk.Frame(button_card, bg=PANEL)
        grid.pack(fill="x", padx=16, pady=(0, 16))

        for index, name in enumerate(self.button_state_vars):
            row = index // 4
            col = index % 4

            item = tk.Frame(grid, bg=PANEL_2, width=150, height=78)
            item.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            item.grid_propagate(False)

            tk.Label(item, text=name, bg=PANEL_2, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(pady=(12, 4))
            label = tk.Label(
                item,
                textvariable=self.button_state_vars[name],
                bg=PANEL_2,
                fg=MUTED,
                font=("Segoe UI", 9, "bold"),
            )
            label.pack()
            setattr(self, f"state_label_{name.replace(' ', '_')}", label)

        for col in range(4):
            grid.columnconfigure(col, weight=1)

        relay_card = self._card(page, "Röle Testi")
        relay_card.pack(fill="x", padx=24, pady=(0, 12))

        relay_buttons = tk.Frame(relay_card, bg=PANEL)
        relay_buttons.pack(fill="x", padx=16, pady=(0, 16))
        self._button(relay_buttons, "Röle 1 Test", lambda: self.send_command("RELAY 1 PULSE"), width=18).pack(side="left", padx=5)
        self._button(relay_buttons, "Röle 2 Test", lambda: self.send_command("RELAY 2 PULSE"), width=18).pack(side="left", padx=5)

    def _create_firmware_page(self) -> None:
        page = self._new_page("firmware")
        self._section_title(page, "Firmware")

        card = self._card(page, "Controller Firmware")
        card.pack(fill="x", padx=24, pady=(0, 12))

        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=(0, 16))

        tk.Label(
            inner,
            text="UF2 dosyasını seçip Pico'yu BOOTSEL modunda güncelleyebilirsin.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 10))

        self.firmware_path_var = tk.StringVar(value="Dosya seçilmedi")
        tk.Label(
            inner,
            textvariable=self.firmware_path_var,
            bg=PANEL_2,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
            padx=10,
            pady=8,
        ).pack(fill="x", pady=(0, 10))

        self._button(inner, "UF2 Dosyası Seç", self.choose_uf2).pack(anchor="w")

    def _create_settings_page(self) -> None:
        page = self._new_page("settings")
        self._section_title(page, "Settings")

        card = self._card(page, "Genel Ayarlar")
        card.pack(fill="x", padx=24, pady=(0, 12))

        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=(0, 16))

        self.auto_connect_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            inner,
            text="Program açılınca otomatik bağlan",
            variable=self.auto_connect_var,
            bg=PANEL,
            fg=TEXT,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=PANEL_2,
            font=("Segoe UI", 10),
        ).pack(anchor="w")

    def _create_logs_page(self) -> None:
        page = self._new_page("logs")
        self._section_title(page, "Logs")

        card = self._card(page, "Canlı Seri Haberleşme")
        card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        text_frame = tk.Frame(card, bg=PANEL)
        text_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log = tk.Text(
            text_frame,
            bg="#0d131b",
            fg=TEXT,
            insertbackground=TEXT,
            wrap="word",
            state="disabled",
            bd=0,
            font=("Consolas", 10),
        )
        self.log.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _button(self, parent: tk.Widget, text: str, command, width: int = 15) -> tk.Button:
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
            relief="flat",
            padx=10,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

    def _info_row(self, parent: tk.Widget, row: int, label: str, variable: tk.StringVar) -> None:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).grid(
            row=row, column=0, sticky="w", padx=(0, 16), pady=5
        )
        tk.Label(parent, textvariable=variable, bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(
            row=row, column=1, sticky="w", pady=5
        )

    def refresh_ports(self) -> None:
        ports = list(list_ports.comports())
        values = [f"{p.device} — {p.description}" for p in ports]
        self.port_combo["values"] = values
        if values:
            self.port_combo.current(0)
        else:
            self.port_var.set("")
        self.status_bar_var.set("PORT LİSTESİ YENİLENDİ")

    def toggle_connection(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        selection = self.port_var.get()
        if not selection:
            messagebox.showwarning(APP_TITLE, "Bağlanacak seri port bulunamadı.")
            return

        device = selection.split(" — ", 1)[0]
        try:
            self.serial_port = serial.Serial(device, BAUD_RATE, timeout=0.2)
        except serial.SerialException as exc:
            messagebox.showerror(APP_TITLE, f"Port açılamadı:\n{exc}")
            return

        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

        self.connect_button.configure(text="Bağlantıyı Kes")
        self.connection_var.set("BAĞLI")
        self.connection_indicator.itemconfigure(self.connection_dot, fill=OK)
        self.com_var.set(device)
        self.status_bar_var.set("CONTROLLER BAĞLANDI")
        self._append_log(f"Bağlandı: {device}")
        self.send_command("PING")
        self.send_command("INFO")

    def disconnect(self) -> None:
        self.stop_event.set()
        port = self.serial_port
        self.serial_port = None

        if port:
            try:
                port.close()
            except serial.SerialException:
                pass

        self.connect_button.configure(text="Bağlan")
        self.connection_var.set("BAĞLI DEĞİL")
        self.connection_indicator.itemconfigure(self.connection_dot, fill=BAD)
        self.com_var.set("-")
        self.status_bar_var.set("BAĞLANTI KESİLDİ")
        self._append_log("Bağlantı kesildi.")

    def _reader_loop(self) -> None:
        while not self.stop_event.is_set():
            port = self.serial_port
            if port is None:
                return

            try:
                raw = port.readline()
            except serial.SerialException as exc:
                self.rx_queue.put(f"HATA: {exc}")
                self.after(0, self.disconnect)
                return

            if raw:
                self.rx_queue.put(raw.decode("utf-8", errors="replace").strip())

    def send_command(self, command: str) -> None:
        port = self.serial_port
        if port is None or not port.is_open:
            messagebox.showwarning(APP_TITLE, "Önce Controller cihazına bağlan.")
            return

        try:
            port.write((command + "\n").encode("ascii"))
            port.flush()
            self._append_log(f"> {command}")
        except serial.SerialException as exc:
            messagebox.showerror(APP_TITLE, f"Komut gönderilemedi:\n{exc}")

    def _drain_rx_queue(self) -> None:
        while True:
            try:
                line = self.rx_queue.get_nowait()
            except queue.Empty:
                break

            self._append_log(line)
            self._process_line(line)

        self.after(100, self._drain_rx_queue)

    def _process_line(self, line: str) -> None:
        if line.startswith("PONG"):
            self.connection_var.set("BAĞLI")
            self.status_bar_var.set("CONTROLLER HAZIR")
        elif line.startswith("INFO"):
            parts = line.split()
            for part in parts:
                if part.startswith("VERSION="):
                    self.firmware_var.set(part.split("=", 1)[1])
        elif line.startswith("STATUS"):
            values = {}
            for item in line.split()[1:]:
                if "=" in item:
                    key, value = item.split("=", 1)
                    values[key] = value

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
                self.button_state_vars[name].set("AKTİF" if active else "PASİF")
                label = getattr(self, f"state_label_{name.replace(' ', '_')}")
                label.configure(fg=OK if active else MUTED)

    def choose_uf2(self) -> None:
        path = filedialog.askopenfilename(
            title="Controller UF2 Dosyası Seç",
            filetypes=[("UF2 Firmware", "*.uf2"), ("Tüm Dosyalar", "*.*")],
        )
        if path:
            self.firmware_path_var.set(path)
            self.status_bar_var.set("UF2 DOSYASI SEÇİLDİ")

    def _append_log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if not hasattr(self, "log"):
            return

        self.log.configure(state="normal")
        self.log.insert("end", f"{timestamp}  {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_close(self) -> None:
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    TGControllerManager().mainloop()
