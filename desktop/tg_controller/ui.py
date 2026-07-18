from __future__ import annotations

import ctypes
import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .config import AppConfig, load_config, save_config
from .device_manager import DeviceManager
from .firmware_loader import FirmwareLoader
from .game import GameManager
from .macro import MacroValidationError, compile_macro, example_macro, validate_macro
from .startup import is_autostart_enabled, set_autostart
from .tray import TrayController
from . import __version__

APP_TITLE = f"TG_CONTROLLER_PRO MANAGER V{__version__}"
WM_HOTKEY = 0x0312
VK_F8 = 0x77
HOTKEY_ID_F8 = 1

BG = "#101720"
PANEL = "#182330"
PANEL2 = "#223243"
TEXT = "#f4f7fa"
MUTED = "#9fb0c0"
ACCENT = "#2f8cff"
OK = "#22c55e"
BAD = "#ef4444"
WARN = "#f59e0b"

ROLE_TITLES = {"controller": "CONTROLLER", "p1": "PLAYER 1", "p2": "PLAYER 2"}
POINT_NAMES = {0: "SOL ÜST", 1: "SAĞ ÜST", 2: "SAĞ ALT", 3: "SOL ALT"}


class ManagerApp:
    def __init__(self, root: tk.Tk, start_minimized: bool = False) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1240x820")
        self.root.minsize(1080, 700)
        self.root.configure(bg=BG)

        self.config: AppConfig = load_config()
        # Kullanıcının isteği: ana pencere görünmese de F8 servisi Windows ile açılsın.
        # Bu kayıt yalnız mevcut kullanıcı hesabına yazılır; yönetici yetkisi istemez.
        try:
            set_autostart(self.config.windows_autostart)
        except OSError:
            pass
        self.event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=4000)
        self.device_manager = DeviceManager(self._queue_event)
        self.game_manager = GameManager(self._queue_event)
        self.firmware_loader = FirmwareLoader(self._queue_event)
        self.tray = TrayController(
            on_show=lambda: self.root.after(0, self.show_window),
            on_toggle=lambda: self.root.after(0, self.toggle_motion),
            on_quit=lambda: self.root.after(0, self.close_app),
        )

        self.motion_active = False
        self.motion_var = tk.StringVar(value="SİLAHLAR PASİF — F8 İLE AKTİF YAP")
        self.game_status_var = tk.StringVar(value="Oyun: durdu")
        self.macro_status_var = tk.StringVar(value="Makro: bekliyor")
        self.credit_var = tk.StringVar(value="0")
        self.relay_awake_var = tk.StringVar(value="UYKUDA — kredi bekliyor")
        self.maintenance_var = tk.StringVar(value="NORMAL")

        self.device_vars: dict[str, dict[str, tk.StringVar]] = {}
        for role in ROLE_TITLES:
            self.device_vars[role] = {
                "status": tk.StringVar(value="BAĞLI DEĞİL"),
                "port": tk.StringVar(value="-"),
                "version": tk.StringVar(value="-"),
            }

        self.gun_values: dict[str, dict[str, tk.Variable]] = {}
        for role in ("p1", "p2"):
            smoothing = self.config.p1_smoothing if role == "p1" else self.config.p2_smoothing
            self.gun_values[role] = {
                "raw_x": tk.StringVar(value="0"),
                "raw_y": tk.StringVar(value="0"),
                "mapped_x": tk.StringVar(value="0"),
                "mapped_y": tk.StringVar(value="0"),
                "gp19": tk.StringVar(value="-"),
                "motion": tk.StringVar(value="PASİF"),
                "calibrated": tk.StringVar(value="YOK"),
                "quality": tk.StringVar(value="0"),
                "axis": tk.StringVar(value="-"),
                "smoothing": tk.IntVar(value=smoothing),
                "cal_message": tk.StringVar(value="Kalibrasyon bekleniyor."),
            }

        self.controller_buttons: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="PASİF")
            for key in ("C", "S1", "T1", "B1", "S2", "T2", "B2", "R1", "R2")
        }
        self.last_controller = {key: "0" for key in ("S1", "S2", "T1", "T2")}
        self.controller_status: dict[str, str] = {}
        self.gun_status: dict[str, dict[str, str]] = {"p1": {}, "p2": {}}

        self.calibration_player: str | None = None
        self.calibration_step = 0
        self.calibration_window: tk.Toplevel | None = None
        self.calibration_canvas: tk.Canvas | None = None
        self.calibration_select_mode = False
        self.pre_calibration_motion = False
        self.test_enabled = False
        self.test_canvas: tk.Canvas | None = None

        self.hotkey_registered = False
        self._auto_start_attempted = False
        self._last_auto_start_attempt = 0.0
        self._closing = False

        self._build_style()
        self._build_ui()
        self._load_config_to_ui()
        self._register_hotkey()
        self.tray.start()
        self.device_manager.start()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.bind("<Control-q>", lambda _event: self.close_app())
        self.root.after(80, self._poll_hotkey)
        self.root.after(100, self._process_events)
        self.root.after(500, self._periodic_tasks)
        self.root.after(2000, self._renew_passive_lease)
        self.root.after(30000, self._maintenance_keepalive)

        if start_minimized or self.config.start_minimized:
            self.root.after(250, self.hide_window)

    def _queue_event(self, event: dict[str, Any]) -> None:
        try:
            self.event_queue.put_nowait(event)
        except queue.Full:
            pass

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Dark.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Dark.TLabel", background=BG, foreground=TEXT)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=PANEL, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="TG_CONTROLLER_PRO", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(side="left", padx=18)
        tk.Label(header, text=f"V{__version__}", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(side="right", padx=18)
        tk.Label(header, textvariable=self.game_status_var, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10, "bold")).pack(side="right", padx=12)

        self.motion_label = tk.Label(
            self.root,
            textvariable=self.motion_var,
            bg=PANEL2,
            fg=BAD,
            height=2,
            font=("Segoe UI", 11, "bold"),
        )
        self.motion_label.pack(fill="x")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.controller_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.p1_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.p2_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.test_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.macro_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.firmware_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=14)
        self.log_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=8)

        for tab, title in (
            (self.dashboard_tab, "Dashboard"),
            (self.controller_tab, "Controller / Tuş Testi"),
            (self.p1_tab, "Player 1"),
            (self.p2_tab, "Player 2"),
            (self.test_tab, "Canlı Silah Testi"),
            (self.macro_tab, "Paradise Lost / 1 Kredi"),
            (self.firmware_tab, "Firmware"),
            (self.log_tab, "Loglar"),
        ):
            self.notebook.add(tab, text=title)

        self._build_dashboard()
        self._build_controller()
        self._build_gun_tab("p1", self.p1_tab)
        self._build_gun_tab("p2", self.p2_tab)
        self._build_test_tab()
        self._build_macro_tab()
        self._build_firmware_tab()
        self._build_log_tab()

    @staticmethod
    def _panel(parent: tk.Widget, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=PANEL2)
        tk.Label(outer, text=title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(10, 6))
        return outer

    @staticmethod
    def _button(parent: tk.Widget, text: str, command, width: int = 16) -> tk.Button:
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
            padx=8,
            pady=8,
            font=("Segoe UI", 9, "bold"),
        )

    def _build_dashboard(self) -> None:
        toolbar = tk.Frame(self.dashboard_tab, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        self._button(toolbar, "Cihazları Yeniden Tara", self.device_manager.force_rescan, 20).pack(side="left", padx=4)
        self._button(toolbar, "F8 — Aktif/Pasif", self.toggle_motion, 18).pack(side="left", padx=4)
        self._button(toolbar, "Programı Gizle", self.hide_window, 14).pack(side="left", padx=4)

        for role in ("controller", "p1", "p2"):
            panel = self._panel(self.dashboard_tab, ROLE_TITLES[role])
            panel.pack(fill="x", pady=5)
            row = tk.Frame(panel, bg=PANEL)
            row.pack(fill="x", padx=14, pady=(0, 12))
            tk.Label(row, textvariable=self.device_vars[role]["status"], bg=PANEL, fg=TEXT,
                     width=18, anchor="w", font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(row, text="Port:", bg=PANEL, fg=MUTED).pack(side="left", padx=(12, 4))
            tk.Label(row, textvariable=self.device_vars[role]["port"], bg=PANEL, fg=TEXT,
                     width=14, anchor="w").pack(side="left")
            tk.Label(row, text="Firmware:", bg=PANEL, fg=MUTED).pack(side="left", padx=(12, 4))
            tk.Label(row, textvariable=self.device_vars[role]["version"], bg=PANEL, fg=TEXT).pack(side="left")

        summary = self._panel(self.dashboard_tab, "Sistem Özeti")
        summary.pack(fill="x", pady=6)
        row = tk.Frame(summary, bg=PANEL)
        row.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(row, text="Ortak kredi:", bg=PANEL, fg=MUTED).pack(side="left")
        tk.Label(row, textvariable=self.credit_var, bg=PANEL, fg=OK,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=8)
        tk.Label(row, text="Titreşim röleleri:", bg=PANEL, fg=MUTED).pack(side="left", padx=(30, 5))
        tk.Label(row, textvariable=self.relay_awake_var, bg=PANEL, fg=WARN,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(row, text="Bakım modu:", bg=PANEL, fg=MUTED).pack(side="left", padx=(30, 5))
        tk.Label(row, textvariable=self.maintenance_var, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")

    def _build_controller(self) -> None:
        status = self._panel(self.controller_tab, "Tuşlar ve Röleler — Canlı Test")
        status.pack(fill="x", pady=4)
        table = tk.Frame(status, bg=PANEL)
        table.pack(fill="x", padx=14, pady=(0, 12))
        headers = ("Pin", "Görev", "HID / Çıkış", "Durum")
        for column, text in enumerate(headers):
            tk.Label(table, text=text, bg=PANEL2, fg=TEXT, padx=8, pady=7,
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=column, sticky="nsew", padx=1, pady=1)
        mappings = (
            ("C", "GP2", "Coin / Ortak kredi", "Klavye 1"),
            ("S1", "GP3", "Player 1 Start", "Klavye 2"),
            ("T1", "GP4", "Player 1 Tetik", "Klavye 3 + Röle 1"),
            ("B1", "GP5", "Player 1 Bomba", "Klavye 4"),
            ("S2", "GP6", "Player 2 Start", "Klavye 5"),
            ("T2", "GP7", "Player 2 Tetik", "Klavye 6 + Röle 2"),
            ("B2", "GP8", "Player 2 Bomba", "Klavye 7"),
            ("R1", "GP27", "Player 1 Röle", "Tetik basılı sürece"),
            ("R2", "GP26", "Player 2 Röle", "Tetik basılı sürece"),
        )
        for row_index, (token, pin, task, output) in enumerate(mappings, start=1):
            for column, value in enumerate((pin, task, output)):
                tk.Label(table, text=value, bg=PANEL, fg=ACCENT if column == 0 else TEXT,
                         anchor="w", padx=8, pady=6).grid(row=row_index, column=column, sticky="nsew", padx=1, pady=1)
            tk.Label(table, textvariable=self.controller_buttons[token], bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 10, "bold"), padx=8, pady=6).grid(
                         row=row_index, column=3, sticky="nsew", padx=1, pady=1)
        for column, weight in enumerate((1, 3, 3, 1)):
            table.grid_columnconfigure(column, weight=weight)

        settings_panel = self._panel(self.controller_tab, "Röle Güvenlik Ayarları")
        settings_panel.pack(fill="x", pady=8)
        form = tk.Frame(settings_panel, bg=PANEL)
        form.pack(fill="x", padx=14, pady=(0, 12))
        self.relay_active_low_var = tk.BooleanVar(value=self.config.relay_active_low)
        self.relay_idle_var = tk.IntVar(value=self.config.relay_inactivity_seconds)
        self.key_pulse_var = tk.IntVar(value=self.config.key_pulse_ms)
        tk.Checkbutton(form, text="Röle modülü aktif LOW", variable=self.relay_active_low_var,
                       bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                       activeforeground=TEXT).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        tk.Label(form, text="Hareketsizlik süresi (sn):", bg=PANEL, fg=MUTED).grid(row=0, column=1, padx=(20, 4))
        tk.Spinbox(form, from_=0, to=3600, textvariable=self.relay_idle_var, width=8,
                   bg=PANEL2, fg=TEXT).grid(row=0, column=2, sticky="w")
        tk.Label(form, text="Coin/Start/Bomba darbesi (ms):", bg=PANEL, fg=MUTED).grid(row=0, column=3, padx=(20, 4))
        tk.Spinbox(form, from_=20, to=500, textvariable=self.key_pulse_var, width=8,
                   bg=PANEL2, fg=TEXT).grid(row=0, column=4, sticky="w")
        self._button(form, "Uygula ve Kaydet", self.apply_controller_settings, 17).grid(row=0, column=5, padx=12)
        self._button(form, "Röleleri Uyut", lambda: self.send("controller", "RELAY SLEEP"), 14).grid(row=1, column=0, padx=6, pady=6)
        self._button(form, "Röleleri Uyandır", lambda: self.send("controller", "RELAY WAKE"), 16).grid(row=1, column=1, columnspan=2, padx=6, pady=6)
        self._button(form, "Krediyi Sıfırla", lambda: self.send("controller", "CREDIT CLEAR"), 16).grid(row=1, column=3, columnspan=2, padx=6, pady=6)

    def _build_gun_tab(self, role: str, tab: ttk.Frame) -> None:
        values = self.gun_values[role]
        live = self._panel(tab, "Canlı Değerler")
        live.pack(fill="x", pady=4)
        grid = tk.Frame(live, bg=PANEL)
        grid.pack(fill="x", padx=14, pady=(0, 12))
        fields = (
            ("Ham X", values["raw_x"]), ("Ham Y", values["raw_y"]),
            ("Ekran X", values["mapped_x"]), ("Ekran Y", values["mapped_y"]),
            ("GP19 DIP", values["gp19"]), ("Hareket", values["motion"]),
            ("Kalibrasyon", values["calibrated"]), ("Kalite", values["quality"]),
            ("Otomatik eksen", values["axis"]),
        )
        for index, (label, variable) in enumerate(fields):
            row = index // 4
            column = index % 4
            cell = tk.Frame(grid, bg=PANEL)
            cell.grid(row=row, column=column, sticky="nsew", padx=8, pady=6)
            tk.Label(cell, text=label, bg=PANEL, fg=MUTED).pack(anchor="w")
            tk.Label(cell, textvariable=variable, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")
            grid.grid_columnconfigure(column, weight=1)

        cal = self._panel(tab, "Profesyonel 4 Köşe Kalibrasyonu")
        cal.pack(fill="x", pady=8)
        row = tk.Frame(cal, bg=PANEL)
        row.pack(fill="x", padx=14, pady=(0, 8))
        self._button(row, "Kalibrasyonu Başlat", lambda r=role: self.begin_calibration(r), 20).pack(side="left", padx=4)
        self._button(row, "Kalibrasyonu Sıfırla", lambda r=role: self.reset_calibration(r), 20).pack(side="left", padx=4)
        tk.Label(cal, textvariable=values["cal_message"], bg=PANEL, fg=WARN,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(0, 12))

        smooth = self._panel(tab, "İvmeli Titreme Engelleme")
        smooth.pack(fill="x", pady=4)
        row2 = tk.Frame(smooth, bg=PANEL)
        row2.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(row2, text="0 = kapalı / 10 = en güçlü", bg=PANEL, fg=MUTED).pack(side="left")
        tk.Scale(row2, from_=0, to=10, orient="horizontal", variable=values["smoothing"],
                 length=430, bg=PANEL, fg=TEXT, troughcolor=PANEL2,
                 highlightthickness=0).pack(side="left", padx=16)
        self._button(row2, "Pico'ya Uygula", lambda r=role: self.apply_smoothing(r), 18).pack(side="left")

    def _build_test_tab(self) -> None:
        toolbar = tk.Frame(self.test_tab, bg=BG)
        toolbar.pack(fill="x", pady=(0, 8))
        self._button(toolbar, "Canlı Testi Başlat", self.start_live_test, 18).pack(side="left", padx=4)
        self._button(toolbar, "Testi Durdur", self.stop_live_test, 14).pack(side="left", padx=4)
        tk.Label(toolbar, text="Bu test silah HID mouse'unu açmadan seri X/Y ile iki nişangâhı gösterir.",
                 bg=BG, fg=MUTED).pack(side="left", padx=16)
        self.test_canvas = tk.Canvas(self.test_tab, bg="black", highlightthickness=1, highlightbackground=PANEL2)
        self.test_canvas.pack(fill="both", expand=True)

    def _build_macro_tab(self) -> None:
        panel = self._panel(self.macro_tab, "Paradise Lost Başlatma")
        panel.pack(fill="x", pady=4)
        form = tk.Frame(panel, bg=PANEL)
        form.pack(fill="x", padx=14, pady=(0, 12))
        self.game_path_var = tk.StringVar(value=self.config.game_path)
        self.game_args_var = tk.StringVar(value=self.config.game_arguments)
        self.workdir_var = tk.StringVar(value=self.config.working_directory)
        self.macro_delay_var = tk.IntVar(value=self.config.macro_delay_seconds)
        self.macro_enabled_var = tk.BooleanVar(value=self.config.macro_enabled)
        self.auto_start_var = tk.BooleanVar(value=self.config.auto_start_game)
        self.auto_restart_var = tk.BooleanVar(value=self.config.auto_restart_game)
        self.require_devices_var = tk.BooleanVar(value=self.config.require_all_devices)
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())

        labels = ("Oyun EXE", "Ek argümanlar", "Çalışma klasörü")
        variables = (self.game_path_var, self.game_args_var, self.workdir_var)
        for row, (label, variable) in enumerate(zip(labels, variables)):
            tk.Label(form, text=label, bg=PANEL, fg=MUTED).grid(row=row, column=0, sticky="w", padx=4, pady=5)
            tk.Entry(form, textvariable=variable, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                     width=85).grid(row=row, column=1, sticky="ew", padx=6, pady=5)
        self._button(form, "Seç", self.choose_game, 8).grid(row=0, column=2, padx=4)
        form.grid_columnconfigure(1, weight=1)

        options = tk.Frame(panel, bg=PANEL)
        options.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(options, text="Oyun açılış bekleme (0–999 sn):", bg=PANEL, fg=MUTED).pack(side="left")
        tk.Spinbox(options, from_=0, to=999, textvariable=self.macro_delay_var, width=8,
                   bg=PANEL2, fg=TEXT).pack(side="left", padx=6)
        for text, variable in (
            ("1 kredi makrosu açık", self.macro_enabled_var),
            ("Windows açılınca oyun", self.auto_start_var),
            ("Oyun kapanırsa tekrar aç", self.auto_restart_var),
            ("3 Pico bağlı olsun", self.require_devices_var),
            ("Program Windows ile başlasın", self.autostart_var),
        ):
            tk.Checkbutton(options, text=text, variable=variable, bg=PANEL, fg=TEXT,
                           selectcolor=PANEL2, activebackground=PANEL,
                           activeforeground=TEXT).pack(side="left", padx=7)

        editor = self._panel(self.macro_tab, "Pico'da Saklanacak Operatör Makrosu — JSON")
        editor.pack(fill="both", expand=True, pady=8)
        self.macro_text = tk.Text(editor, height=13, bg="#0d131b", fg=TEXT,
                                  insertbackground=TEXT, font=("Consolas", 10), wrap="none")
        self.macro_text.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        buttons = tk.Frame(editor, bg=PANEL)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        self._button(buttons, "Ayarları Kaydet", self.save_game_settings, 16).pack(side="left", padx=4)
        self._button(buttons, "Makroyu Pico'ya Yaz", self.upload_macro, 19).pack(side="left", padx=4)
        self._button(buttons, "Örnek F1/F2 Getir", self.insert_example_macro, 18).pack(side="left", padx=4)
        self._button(buttons, "Oyunu Başlat", self.launch_game, 14).pack(side="left", padx=4)
        self._button(buttons, "Makroyu Şimdi Çalıştır", self.run_macro_now, 22).pack(side="left", padx=4)
        self._button(buttons, "Sayaç/Makro İptal", self.cancel_macro, 18).pack(side="left", padx=4)
        tk.Label(buttons, textvariable=self.macro_status_var, bg=PANEL, fg=WARN,
                 font=("Segoe UI", 10, "bold")).pack(side="right", padx=8)

    def _build_firmware_tab(self) -> None:
        info = tk.Label(
            self.firmware_tab,
            text="Doğru UF2'yi seçin. Program Pico'ya BOOTSEL komutu gönderir, RPI-RP2 sürücüsünü bekler ve dosyayı kopyalar.",
            bg=BG, fg=TEXT, wraplength=1000, justify="left",
        )
        info.pack(anchor="w", pady=(0, 12))
        self.uf2_vars = {role: tk.StringVar() for role in ROLE_TITLES}
        default_names = {
            "controller": "TG_CONTROLLER_PRO_CONTROLLER_V4.uf2",
            "p1": "TG_CONTROLLER_PRO_GUN_P1_V4.uf2",
            "p2": "TG_CONTROLLER_PRO_GUN_P2_V4.uf2",
        }
        for role in ("controller", "p1", "p2"):
            panel = self._panel(self.firmware_tab, ROLE_TITLES[role])
            panel.pack(fill="x", pady=5)
            row = tk.Frame(panel, bg=PANEL)
            row.pack(fill="x", padx=14, pady=(0, 12))
            tk.Entry(row, textvariable=self.uf2_vars[role], bg=PANEL2, fg=TEXT,
                     insertbackground=TEXT, width=80).pack(side="left", fill="x", expand=True, padx=4)
            self._button(row, "Dosya Seç", lambda r=role: self.choose_uf2(r), 12).pack(side="left", padx=4)
            self._button(row, "Yükle", lambda r=role: self.update_firmware(r), 10).pack(side="left", padx=4)
            tk.Label(row, text=default_names[role], bg=PANEL, fg=MUTED).pack(side="left", padx=8)
        self.firmware_status_var = tk.StringVar(value="Hazır")
        tk.Label(self.firmware_tab, textvariable=self.firmware_status_var, bg=BG, fg=WARN,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=12)

    def _build_log_tab(self) -> None:
        self.log_text = tk.Text(self.log_tab, state="disabled", bg="#0d131b", fg=TEXT,
                                insertbackground=TEXT, font=("Consolas", 9), wrap="none")
        y_scroll = ttk.Scrollbar(self.log_tab, orient="vertical", command=self.log_text.yview)
        x_scroll = ttk.Scrollbar(self.log_tab, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.log_tab.columnconfigure(0, weight=1)
        self.log_tab.rowconfigure(0, weight=1)

    def _load_config_to_ui(self) -> None:
        self.macro_text.delete("1.0", "end")
        self.macro_text.insert("1.0", json.dumps(self.config.macro_steps, ensure_ascii=False, indent=2))

    def _process_events(self) -> None:
        for _ in range(250):
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_event(event)
            except Exception as exc:
                self._log(f"UI olay hatası: {exc}")
        if not self._closing:
            self.root.after(100, self._process_events)

    def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "identified":
            role = str(event["role"])
            self.device_vars[role]["status"].set("BAĞLI / HAZIR")
            self.device_vars[role]["port"].set(str(event["port"]))
            values = self._values(str(event["line"]))
            self.device_vars[role]["version"].set(values.get("VERSION", "-"))
            self._log(f"{ROLE_TITLES[role]} tanındı: {event['port']}")
            if role in ("p1", "p2"):
                force_passive = (
                    not self.motion_active
                    or self.calibration_player is not None
                    or self.calibration_select_mode
                )
                self.send(role, "MOTION OFF" if force_passive else "MOTION ON")
                self.send(role, "CONFIG")
            else:
                self.send("controller", "CONFIG")
        elif event_type == "disconnected":
            role = str(event["role"])
            self.device_vars[role]["status"].set("BAĞLI DEĞİL")
            self.device_vars[role]["port"].set("-")
            self.device_vars[role]["version"].set("-")
            self._log(f"{ROLE_TITLES[role]} bağlantısı kesildi")
            if self.calibration_player and role in (self.calibration_player, "controller"):
                self.finish_calibration(success=False, message="USB bağlantısı kesildi; önceki ayar korundu.")
        elif event_type == "health":
            role = str(event["role"])
            self.device_vars[role]["status"].set("BAĞLI / HAZIR" if event["responsive"] else "BAĞLI / VERİ BEKLENİYOR")
        elif event_type == "line":
            self._handle_device_line(str(event["role"]), str(event["line"]))
        elif event_type == "game_started":
            self.game_status_var.set(f"Oyun: çalışıyor (PID {event['pid']})")
        elif event_type == "game_already_running":
            self.game_status_var.set("Oyun: zaten açık")
        elif event_type == "game_exited":
            self.game_status_var.set(f"Oyun: kapandı ({event['return_code']})")
        elif event_type == "game_stopped":
            self.game_status_var.set("Oyun: durdu")
        elif event_type == "game_error":
            self.game_status_var.set("Oyun: hata")
            messagebox.showerror(APP_TITLE, str(event["message"]))
        elif event_type == "macro_countdown":
            self.macro_status_var.set(f"Makro: {event['remaining']} sn")
        elif event_type == "macro_requested":
            self.macro_status_var.set("Makro: Pico'ya başlatma gönderildi")
        elif event_type == "macro_uploaded":
            self.macro_status_var.set("Makro: doğrulandı ve Controller flash'ına kaydedildi")
        elif event_type == "macro_cancelled":
            self.macro_status_var.set(f"Makro: iptal — {event['reason']}")
        elif event_type == "macro_error":
            self.macro_status_var.set(f"Makro hata: {event['message']}")
        elif event_type == "restart_wait":
            self.game_status_var.set(f"Oyun: {event['seconds']} sn sonra yeniden açılacak")
        elif event_type == "firmware_status":
            self.firmware_status_var.set(f"{ROLE_TITLES[event['role']]}: {event['message']}")
        elif event_type == "firmware_done":
            self.firmware_status_var.set(f"{ROLE_TITLES[event['role']]} yüklendi: {event['file']}")
        elif event_type == "firmware_error":
            self.firmware_status_var.set(f"Hata: {event['message']}")
            messagebox.showerror(APP_TITLE, str(event["message"]))

    def _handle_device_line(self, role: str, line: str) -> None:
        self._log(f"[{role.upper()}] {line}")
        if line.startswith("STATUS") and role == "controller":
            values = self._values(line)
            self.controller_status = values
            self.credit_var.set(values.get("CREDIT", "0"))
            self.relay_awake_var.set("AKTİF" if values.get("RELAYAWAKE") == "1" else "UYKUDA — kredi bekliyor")
            self.maintenance_var.set("BAKIM / KALİBRASYON" if values.get("MAINT") == "1" else "NORMAL")
            for key in self.controller_buttons:
                self.controller_buttons[key].set("AKTİF" if values.get(key) == "1" else "PASİF")

            s1_edge = values.get("S1") == "1" and self.last_controller.get("S1") != "1"
            s2_edge = values.get("S2") == "1" and self.last_controller.get("S2") != "1"
            t1_edge = values.get("T1") == "1" and self.last_controller.get("T1") != "1"
            t2_edge = values.get("T2") == "1" and self.last_controller.get("T2") != "1"

            maintenance_recovery = values.get("MAINT") == "1"
            calibration_requested = values.get("CALREQ") == "1"
            if (calibration_requested or maintenance_recovery) and not self.calibration_player and not self.calibration_select_mode:
                if calibration_requested:
                    self.send("controller", "CAL ACK")
                self.open_player_selection()
            if self.calibration_select_mode:
                if s1_edge:
                    self.begin_calibration("p1", maintenance_already_active=True)
                elif s2_edge:
                    self.begin_calibration("p2", maintenance_already_active=True)
            elif self.calibration_player == "p1" and t1_edge:
                self.capture_calibration()
            elif self.calibration_player == "p2" and t2_edge:
                self.capture_calibration()

            self.last_controller.update({key: values.get(key, "0") for key in self.last_controller})
        elif line.startswith("GUNSTATUS") and role in ("p1", "p2"):
            values = self._values(line)
            self.gun_status[role] = values
            gun = self.gun_values[role]
            gun["raw_x"].set(values.get("X", "0"))
            gun["raw_y"].set(values.get("Y", "0"))
            gun["mapped_x"].set(values.get("MX", "0"))
            gun["mapped_y"].set(values.get("MY", "0"))
            gun["gp19"].set("AKTİF" if values.get("GP19") == "1" else "PASİF")
            gun["motion"].set("AKTİF" if values.get("MOTION") == "1" else "PASİF")
            gun["calibrated"].set("GEÇERLİ" if values.get("CAL") == "1" else "YOK")
            gun["quality"].set(values.get("QUALITY", "0"))
            gun["axis"].set(
                f"X/Y değişim:{values.get('SWAP','0')}  X ters:{values.get('INVX','0')}  Y ters:{values.get('INVY','0')}"
            )
            if "SMOOTH" in values:
                gun["smoothing"].set(int(values["SMOOTH"]))
        elif role in ("p1", "p2") and line.startswith("EVENT CALREADY"):
            values = self._values(line)
            self.calibration_step = int(values.get("INDEX", "0"))
            self._draw_calibration_target()
            self.gun_values[role]["cal_message"].set(f"{POINT_NAMES[self.calibration_step]} hedefini onayla.")
        elif role in ("p1", "p2") and line.startswith("EVENT CALPOINT"):
            values = self._values(line)
            index = int(values.get("INDEX", "0"))
            self.gun_values[role]["cal_message"].set(
                f"{POINT_NAMES[index]} kaydedildi: X={values.get('X')} Y={values.get('Y')}"
            )
        elif role in ("p1", "p2") and line.startswith("EVENT CALUNSTABLE"):
            values = self._values(line)
            index = int(values.get("INDEX", "0"))
            self.calibration_step = index
            self._draw_calibration_target()
            self.gun_values[role]["cal_message"].set(
                f"{POINT_NAMES.get(index, 'Köşe')} sırasında silah hareket etti. "
                f"Sabit tutup yeniden onayla (sapma X={values.get('SPREADX','-')}, "
                f"Y={values.get('SPREADY','-')})."
            )
        elif role in ("p1", "p2") and line.startswith("EVENT CALDONE"):
            values = self._values(line)
            self.finish_calibration(True, f"Kalibrasyon tamamlandı. Kalite: {values.get('QUALITY','-')}/100")
        elif role in ("p1", "p2") and line.startswith("EVENT CALERROR"):
            values = self._values(line)
            self.finish_calibration(False, f"Kalibrasyon hatası: {values.get('REASON','bilinmiyor')}")
        elif line.startswith("EVENT MACRO START"):
            self.macro_status_var.set("Makro: çalışıyor")
        elif line.startswith("EVENT MACRO STEP"):
            values = self._values(line)
            self.macro_status_var.set(f"Makro: adım {values.get('STEP','-')}/{values.get('TOTAL','-')}")
        elif line.startswith("EVENT MACRO DONE"):
            self.macro_status_var.set("Makro: tamamlandı")
        elif line.startswith("EVENT MACRO STOPPED"):
            self.macro_status_var.set("Makro: durduruldu")
        elif line.startswith("CONFIG") and role == "controller":
            values = self._values(line)
            self.relay_active_low_var.set(values.get("RELAYLOW") == "1")
            if "IDLE" in values:
                self.relay_idle_var.set(int(values["IDLE"]))
            if "KEYPULSE" in values:
                self.key_pulse_var.set(int(values["KEYPULSE"]))
        elif line.startswith("CONFIG") and role in ("p1", "p2"):
            values = self._values(line)
            if "SMOOTH" in values:
                self.gun_values[role]["smoothing"].set(int(values["SMOOTH"]))
            self.gun_values[role]["calibrated"].set(
                "GEÇERLİ" if values.get("CAL") == "1" else "YOK"
            )
            self.gun_values[role]["quality"].set(values.get("QUALITY", "0"))

    @staticmethod
    def _values(line: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for token in line.split()[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                values[key] = value
        return values

    def send(self, role: str, command: str, warn: bool = False) -> bool:
        sent = self.device_manager.send(role, command)
        if sent:
            self._log(f"[{role.upper()}] > {command}")
        elif warn:
            messagebox.showwarning(APP_TITLE, f"{ROLE_TITLES[role]} bağlı değil.")
        return sent

    def toggle_motion(self) -> None:
        if self.calibration_player is not None or self.calibration_select_mode:
            self.send("p1", "MOTION OFF")
            self.send("p2", "MOTION OFF")
            self._log("F8 kalibrasyon sırasında kilitlidir; iki silah pasif tutuldu.")
            return
        self.motion_active = not self.motion_active
        if self.motion_active:
            self.motion_var.set("SİLAHLAR AKTİF — F8 İLE PASİF YAP")
            self.motion_label.configure(fg=OK)
        else:
            self.motion_var.set("SİLAHLAR PASİF — F8 İLE AKTİF YAP")
            self.motion_label.configure(fg=BAD)
        command = "MOTION ON" if self.motion_active else "MOTION OFF"
        self.send("p1", command)
        self.send("p2", command)

    def _renew_passive_lease(self) -> None:
        # Kalibrasyon/oyuncu seçimi boyunca, kalibrasyon öncesinde silahlar aktif
        # olsa bile 5 saniyelik Gun Pico pasiflik kirasını sürekli yenile.
        force_passive = self.calibration_player is not None or self.calibration_select_mode
        if not self._closing and (not self.motion_active or force_passive):
            self.send("p1", "MOTION OFF")
            self.send("p2", "MOTION OFF")
        if not self._closing:
            self.root.after(2000, self._renew_passive_lease)

    def _maintenance_keepalive(self) -> None:
        if not self._closing and (self.calibration_player or self.calibration_select_mode):
            self.send("controller", "MAINT KEEP")
        if not self._closing:
            self.root.after(30000, self._maintenance_keepalive)

    def open_player_selection(self) -> None:
        self.show_window()
        self.calibration_select_mode = True
        self.pre_calibration_motion = self.motion_active
        self.send("p1", "MOTION OFF")
        self.send("p2", "MOTION OFF")
        window = tk.Toplevel(self.root)
        self.calibration_window = window
        window.attributes("-fullscreen", True)
        window.configure(bg="black")
        window.bind("<Escape>", lambda _event: self.finish_calibration(False, "Kalibrasyon iptal edildi."))
        canvas = tk.Canvas(window, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_text(
            window.winfo_screenwidth() // 2,
            window.winfo_screenheight() // 2 - 40,
            text="KALİBRE EDİLECEK SİLAHI SEÇ",
            fill="white",
            font=("Segoe UI", 28, "bold"),
        )
        canvas.create_text(
            window.winfo_screenwidth() // 2,
            window.winfo_screenheight() // 2 + 30,
            text="PLAYER 1 START veya PLAYER 2 START tuşuna bas",
            fill="#2f8cff",
            font=("Segoe UI", 20, "bold"),
        )

    def begin_calibration(self, role: str, maintenance_already_active: bool = False) -> None:
        if not self.device_manager.all_required_connected():
            messagebox.showwarning(APP_TITLE, "Kalibrasyon için Controller, P1 ve P2 bağlı olmalıdır.")
            return
        if self.calibration_window and self.calibration_window.winfo_exists():
            self.calibration_window.destroy()
        self.calibration_select_mode = False
        self.calibration_player = role
        self.calibration_step = 0
        self.pre_calibration_motion = self.motion_active
        if not maintenance_already_active:
            self.send("controller", "MAINT START")
        self.send("p1", "MOTION OFF")
        self.send("p2", "MOTION OFF")
        if not self.send(role, "CAL START", warn=True):
            self.send("controller", "MAINT END")
            self.calibration_player = None
            return

        window = tk.Toplevel(self.root)
        self.calibration_window = window
        window.attributes("-fullscreen", True)
        window.configure(bg="black")
        window.bind("<Escape>", lambda _event: self.finish_calibration(False, "Kalibrasyon iptal edildi."))
        self.calibration_canvas = tk.Canvas(window, bg="black", highlightthickness=0)
        self.calibration_canvas.pack(fill="both", expand=True)
        self.calibration_canvas.bind("<Button-1>", lambda _event: self.capture_calibration())
        window.after(100, self._draw_calibration_target)
        self.gun_values[role]["cal_message"].set("SOL ÜST hedefini tetik veya normal mouse ile onayla.")

    def capture_calibration(self) -> None:
        if self.calibration_player:
            self.send(self.calibration_player, "CAL CAPTURE")

    def _draw_calibration_target(self) -> None:
        canvas = self.calibration_canvas
        if not canvas or not self.calibration_player or self.calibration_step not in POINT_NAMES:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 600)
        margin = 55
        targets = ((margin, margin), (width - margin, margin), (width - margin, height - margin), (margin, height - margin))
        x, y = targets[self.calibration_step]
        canvas.create_oval(x - 24, y - 24, x + 24, y + 24, outline="red", width=5)
        canvas.create_line(x - 38, y, x + 38, y, fill="white", width=2)
        canvas.create_line(x, y - 38, x, y + 38, fill="white", width=2)
        canvas.create_text(width // 2, 40,
                           text=f"{POINT_NAMES[self.calibration_step]} — TETİĞE BAS veya NORMAL MOUSE İLE TIKLA",
                           fill="white", font=("Segoe UI", 20, "bold"))
        canvas.create_text(width // 2, height - 30,
                           text="Kalibrasyonda oyun tuşları ve titreşim röleleri kilitlidir.",
                           fill="#f59e0b", font=("Segoe UI", 13, "bold"))

    def finish_calibration(self, success: bool, message: str) -> None:
        role = self.calibration_player
        if role and not success:
            self.send(role, "CAL CANCEL")
        self.send("controller", "MAINT END")
        self.calibration_player = None
        self.calibration_select_mode = False
        if self.calibration_window and self.calibration_window.winfo_exists():
            self.calibration_window.destroy()
        self.calibration_window = None
        self.calibration_canvas = None
        if self.pre_calibration_motion:
            self.motion_active = False
            self.toggle_motion()
        else:
            self.motion_active = False
            self.motion_var.set("SİLAHLAR PASİF — F8 İLE AKTİF YAP")
            self.motion_label.configure(fg=BAD)
            self.send("p1", "MOTION OFF")
            self.send("p2", "MOTION OFF")
        if role:
            self.gun_values[role]["cal_message"].set(message)
        if success:
            messagebox.showinfo(APP_TITLE, message)
        else:
            messagebox.showwarning(APP_TITLE, message)

    def reset_calibration(self, role: str) -> None:
        if messagebox.askyesno(APP_TITLE, "Kalibrasyon silinsin mi? Titreme ayarı korunur."):
            self.send(role, "CAL RESET", warn=True)

    def apply_smoothing(self, role: str) -> None:
        value = int(self.gun_values[role]["smoothing"].get())
        self.send(role, f"SET SMOOTH {value}", warn=True)
        self.send(role, "SAVE")
        if role == "p1":
            self.config.p1_smoothing = value
        else:
            self.config.p2_smoothing = value
        save_config(self.config)

    def start_live_test(self) -> None:
        self.test_enabled = True
        self.notebook.select(self.test_tab)

    def stop_live_test(self) -> None:
        self.test_enabled = False
        if self.test_canvas:
            self.test_canvas.delete("all")

    def _draw_live_test(self) -> None:
        if not self.test_enabled or not self.test_canvas:
            return
        canvas = self.test_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 500)
        for role, color, label in (("p1", "#22c55e", "P1"), ("p2", "#ef4444", "P2")):
            values = self.gun_status[role]
            try:
                mx = int(values.get("MX", "0"))
                my = int(values.get("MY", "0"))
            except ValueError:
                continue
            x = int((mx + 32767) / 65534 * width)
            y = int((my + 32767) / 65534 * height)
            canvas.create_oval(x - 16, y - 16, x + 16, y + 16, outline=color, width=3)
            canvas.create_line(x - 26, y, x + 26, y, fill=color, width=2)
            canvas.create_line(x, y - 26, x, y + 26, fill=color, width=2)
            canvas.create_text(x + 24, y - 24, text=label, fill=color, font=("Segoe UI", 11, "bold"))

    def apply_controller_settings(self) -> None:
        try:
            idle = max(0, min(3600, int(self.relay_idle_var.get())))
            pulse = max(20, min(500, int(self.key_pulse_var.get())))
        except (TypeError, ValueError, tk.TclError):
            messagebox.showerror(APP_TITLE, "Controller ayarları sayı olmalıdır.")
            return
        active_low = bool(self.relay_active_low_var.get())
        for command in (
            f"SET RELAY_ACTIVE_LOW {int(active_low)}",
            f"SET INACTIVITY_S {idle}",
            f"SET KEY_PULSE_MS {pulse}",
            "SAVE",
        ):
            if not self.send("controller", command, warn=True):
                return
        self.config.relay_active_low = active_low
        self.config.relay_inactivity_seconds = idle
        self.config.key_pulse_ms = pulse
        save_config(self.config)

    def choose_game(self) -> None:
        path = filedialog.askopenfilename(
            title="Paradise Lost Farcry_R.exe dosyasını seç",
            filetypes=(("Windows uygulaması", "*.exe"), ("Tüm dosyalar", "*.*")),
        )
        if path:
            self.game_path_var.set(path)
            self.workdir_var.set(str(Path(path).parent))

    def save_game_settings(self, show_message: bool = True) -> bool:
        try:
            raw = json.loads(self.macro_text.get("1.0", "end").strip() or "[]")
            steps = validate_macro(raw)
            delay = max(0, min(999, int(self.macro_delay_var.get())))
        except (json.JSONDecodeError, MacroValidationError, ValueError, tk.TclError) as exc:
            messagebox.showerror(APP_TITLE, f"Makro/ayar hatası: {exc}")
            return False
        if self.macro_enabled_var.get() and not steps:
            messagebox.showerror(APP_TITLE, "Makro açıkken en az bir doğrulanmış adım olmalıdır.")
            return False
        self.config.game_path = self.game_path_var.get().strip()
        self.config.game_arguments = self.game_args_var.get().strip()
        self.config.working_directory = self.workdir_var.get().strip()
        self.config.macro_delay_seconds = delay
        self.config.macro_enabled = bool(self.macro_enabled_var.get())
        self.config.macro_steps = steps
        self.config.auto_start_game = bool(self.auto_start_var.get())
        self.config.auto_restart_game = bool(self.auto_restart_var.get())
        self.config.require_all_devices = bool(self.require_devices_var.get())
        self.config.windows_autostart = bool(self.autostart_var.get())
        save_config(self.config)
        try:
            set_autostart(self.config.windows_autostart)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Windows başlangıç ayarı yazılamadı: {exc}")
            return False
        if show_message:
            messagebox.showinfo(APP_TITLE, "Oyun ve başlangıç ayarları kaydedildi.")
        return True

    def upload_macro(self) -> None:
        if not self.save_game_settings(show_message=False):
            return
        try:
            compiled = compile_macro(self.config.macro_steps)
        except MacroValidationError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        def worker() -> None:
            commands = ["MACRO CLEAR"]
            commands.extend(f"MACRO ADD {step.keycode} {step.hold_ms} {step.wait_ms}" for step in compiled)
            commands.append(f"MACRO ENABLE {int(self.config.macro_enabled and bool(compiled))}")
            commands.append("SAVE")
            for command in commands:
                if not self.device_manager.send("controller", command):
                    self._queue_event({"type": "macro_error", "message": "Controller bağlantısı kesildi"})
                    return
                time.sleep(0.04)
            self._queue_event({"type": "macro_uploaded"})

        threading.Thread(target=worker, daemon=True).start()

    def insert_example_macro(self) -> None:
        self.macro_text.delete("1.0", "end")
        self.macro_text.insert("1.0", json.dumps(example_macro(), ensure_ascii=False, indent=2))
        self.macro_enabled_var.set(False)
        messagebox.showinfo(
            APP_TITLE,
            "F1/F2 yalnız biçim örneğidir. Kabindeki gerçek operatör tuş sırası doğrulanmadan makroyu açmayın.",
        )

    def launch_game(self) -> None:
        if not self.save_game_settings(show_message=False):
            return
        if self.config.require_all_devices and not self.device_manager.all_required_connected():
            messagebox.showwarning(APP_TITLE, "Controller, P1 ve P2 bağlı olmadan oyun başlatılmadı.")
            return
        self.game_manager.launch(self.config, lambda: self.send("controller", "MACRO START"))

    def run_macro_now(self) -> None:
        if self.config.macro_enabled:
            self.send("controller", "MACRO START", warn=True)
        else:
            messagebox.showwarning(APP_TITLE, "Önce doğrulanmış makroyu etkinleştirip Pico'ya yazın.")

    def cancel_macro(self) -> None:
        self.game_manager.cancel_countdown()
        self.send("controller", "MACRO STOP")
        self.macro_status_var.set("Makro: iptal edildi")

    def choose_uf2(self, role: str) -> None:
        path = filedialog.askopenfilename(title="UF2 dosyasını seç", filetypes=(("UF2 firmware", "*.uf2"),))
        if path:
            self.uf2_vars[role].set(path)

    def update_firmware(self, role: str) -> None:
        path = self.uf2_vars[role].get().strip()
        self.firmware_loader.update(role, path, lambda selected: self.send(selected, "BOOTSEL"))

    def _periodic_tasks(self) -> None:
        self._draw_live_test()
        if self.config.auto_start_game and not self._auto_start_attempted:
            ready = self.device_manager.all_required_connected() or not self.config.require_all_devices
            now = time.monotonic()
            if ready and now - self._last_auto_start_attempt >= 30.0:
                self._last_auto_start_attempt = now
                started = self.game_manager.launch(
                    self.config, lambda: self.send("controller", "MACRO START")
                )
                self._auto_start_attempted = started or self.game_manager.is_game_running(
                    self.config.game_path
                )
        if not self._closing:
            self.root.after(500, self._periodic_tasks)

    def _register_hotkey(self) -> None:
        if os.name != "nt":
            return
        try:
            self.hotkey_registered = bool(
                ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID_F8, 0, VK_F8)
            )
        except Exception:
            self.hotkey_registered = False
        if not self.hotkey_registered:
            self._log("UYARI: F8 genel kısayolu kaydedilemedi; başka bir program F8'i kullanıyor olabilir.")

    def _poll_hotkey(self) -> None:
        if os.name == "nt":
            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
                    ("time", ctypes.c_uint), ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long),
                ]
            message = MSG()
            while ctypes.windll.user32.PeekMessageW(
                ctypes.byref(message), None, WM_HOTKEY, WM_HOTKEY, 1
            ):
                if message.wParam == HOTKEY_ID_F8:
                    self.toggle_motion()
        if not self._closing:
            self.root.after(80, self._poll_hotkey)

    def _log(self, line: str) -> None:
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 3000:
            self.log_text.delete("1.0", "500.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self) -> None:
        self.root.withdraw()

    def close_app(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self.calibration_player:
            self.send(self.calibration_player, "CAL CANCEL")
        self.send("controller", "MAINT END")
        self.send("p1", "MOTION ON")
        self.send("p2", "MOTION ON")
        self.game_manager.cancel_countdown()
        self.device_manager.stop()
        self.tray.stop()
        if self.hotkey_registered and os.name == "nt":
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID_F8)
            except Exception:
                pass
        self.root.after(150, self.root.destroy)
