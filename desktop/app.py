from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import serial
from serial.tools import list_ports


APP_TITLE = "TG CONTROLLER MANAGER V002"
BAUD_RATE = 115200


class TGControllerManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("840x560")
        self.minsize(760, 500)

        self.serial_port: serial.Serial | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.rx_queue: queue.Queue[str] = queue.Queue()

        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Bağlı değil")

        self._build_ui()
        self.refresh_ports()
        self.after(100, self._drain_rx_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Seri port:").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(
            top, textvariable=self.port_var, width=38, state="readonly"
        )
        self.port_combo.grid(row=0, column=1, padx=8, sticky="ew")

        ttk.Button(top, text="Yenile", command=self.refresh_ports).grid(
            row=0, column=2, padx=4
        )
        self.connect_button = ttk.Button(top, text="Bağlan", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=3, padx=4)

        top.columnconfigure(1, weight=1)

        status_frame = ttk.LabelFrame(self, text="Cihaz durumu", padding=12)
        status_frame.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor="w")

        controls = ttk.LabelFrame(self, text="Testler", padding=12)
        controls.pack(fill="x", padx=12, pady=(0, 10))

        ttk.Button(controls, text="Cihaz Bilgisi", command=lambda: self.send_command("INFO")).grid(
            row=0, column=0, padx=5, pady=5, sticky="ew"
        )
        ttk.Button(controls, text="Durumu Oku", command=lambda: self.send_command("STATUS")).grid(
            row=0, column=1, padx=5, pady=5, sticky="ew"
        )
        ttk.Button(controls, text="Röle 1 Test", command=lambda: self.send_command("RELAY 1 PULSE")).grid(
            row=0, column=2, padx=5, pady=5, sticky="ew"
        )
        ttk.Button(controls, text="Röle 2 Test", command=lambda: self.send_command("RELAY 2 PULSE")).grid(
            row=0, column=3, padx=5, pady=5, sticky="ew"
        )

        for i in range(4):
            controls.columnconfigure(i, weight=1)

        log_frame = ttk.LabelFrame(self, text="Canlı kayıt", padding=8)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log = tk.Text(log_frame, wrap="word", state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

    def refresh_ports(self) -> None:
        ports = list(list_ports.comports())
        values = [f"{p.device} — {p.description}" for p in ports]
        self.port_combo["values"] = values
        if values:
            self.port_combo.current(0)
        else:
            self.port_var.set("")

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
        self.status_var.set(f"Bağlandı: {device}")
        self._append_log(f"Bağlandı: {device}")
        self.send_command("PING")

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
        self.status_var.set("Bağlı değil")
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
            if line.startswith("PONG") or line.startswith("INFO"):
                self.status_var.set(line)
        self.after(100, self._drain_rx_queue)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_close(self) -> None:
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    TGControllerManager().mainloop()
