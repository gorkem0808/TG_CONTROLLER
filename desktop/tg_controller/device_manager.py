from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import serial
from serial.tools import list_ports

BAUD_RATE = 115200
USB_VID = 0xCAFE
USB_PIDS = {0x4010, 0x4011, 0x4012}
ROLE_TOKENS = {
    "NAME=TG_CONTROLLER": "controller",
    "NAME=TG_GUN_P1": "p1",
    "NAME=TG_GUN_P2": "p2",
}


@dataclass
class DeviceState:
    role: str
    port: str
    connected: bool = False
    responsive: bool = False
    version: str = "-"
    last_line_at: float = 0.0


class PortConnection:
    def __init__(self, port: str, callback: Callable[[str, str], None]) -> None:
        self.port_name = port
        self.callback = callback
        self.serial: serial.Serial | None = None
        self.stop_event = threading.Event()
        self.write_lock = threading.Lock()
        self.role: str | None = None

    def start(self) -> None:
        self.serial = serial.Serial(
            self.port_name,
            BAUD_RATE,
            timeout=0.2,
            write_timeout=1.0,
        )
        self.serial.dtr = True
        self.serial.rts = True
        self.stop_event.clear()
        threading.Thread(target=self._reader, daemon=True).start()
        time.sleep(0.25)
        self.send("INFO")
        self.send("STATUS")

    def stop(self) -> None:
        self.stop_event.set()
        if self.serial:
            try:
                self.serial.close()
            except serial.SerialException:
                pass
        self.serial = None

    def send(self, command: str) -> None:
        if not self.serial or not self.serial.is_open:
            raise serial.SerialException("Port bağlı değil")
        with self.write_lock:
            self.serial.write((command + "\n").encode("ascii"))
            self.serial.flush()

    def _reader(self) -> None:
        while not self.stop_event.is_set() and self.serial:
            try:
                data = self.serial.readline()
                if data:
                    line = data.decode("utf-8", errors="replace").strip()
                    if line:
                        self.callback(self.port_name, line)
            except serial.SerialException:
                self.callback(self.port_name, "__PORT_ERROR__")
                return


class DeviceManager:
    def __init__(self, callback: Callable[[dict], None]) -> None:
        self.callback = callback
        self.connections: dict[str, PortConnection] = {}
        self.roles: dict[str, PortConnection] = {}
        self.states: dict[str, DeviceState] = {}
        self.stop_event = threading.Event()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=3000)
        self.lock = threading.RLock()

    def start(self) -> None:
        self.stop_event.clear()
        threading.Thread(target=self._scan_loop, daemon=True).start()
        threading.Thread(target=self._event_loop, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()
        with self.lock:
            for connection in list(self.connections.values()):
                connection.stop()
            self.connections.clear()
            self.roles.clear()
            self.states.clear()

    def connected_roles(self) -> set[str]:
        with self.lock:
            return set(self.roles)

    def all_required_connected(self) -> bool:
        with self.lock:
            return all(role in self.roles for role in ("controller", "p1", "p2"))

    def send(self, role: str, command: str) -> bool:
        with self.lock:
            connection = self.roles.get(role)
        if connection is None:
            return False
        try:
            connection.send(command)
            return True
        except serial.SerialException:
            return False

    def snapshot(self) -> dict[str, DeviceState]:
        with self.lock:
            return {key: DeviceState(**vars(value)) for key, value in self.states.items()}

    def force_rescan(self) -> None:
        disconnected: list[tuple[str, str]] = []
        with self.lock:
            disconnected = [(role, connection.port_name) for role, connection in self.roles.items()]
            for connection in list(self.connections.values()):
                connection.stop()
            self.connections.clear()
            self.roles.clear()
            self.states.clear()
        for role, port in disconnected:
            self.callback({"type": "disconnected", "role": role, "port": port})

    def _queue_line(self, port: str, line: str) -> None:
        try:
            self.events.put_nowait((port, line))
        except queue.Full:
            pass

    def _scan_loop(self) -> None:
        while not self.stop_event.is_set():
            present = {
                item.device
                for item in list_ports.comports()
                if item.vid == USB_VID and item.pid in USB_PIDS
            }
            with self.lock:
                for missing in set(self.connections) - present:
                    self._remove_port_locked(missing)

                for port in sorted(present):
                    if port in self.connections:
                        continue
                    connection = PortConnection(port, self._queue_line)
                    try:
                        connection.start()
                    except (serial.SerialException, OSError):
                        continue
                    self.connections[port] = connection
                    self.callback({"type": "port_open", "port": port})

                now = time.monotonic()
                for role, state in list(self.states.items()):
                    responsive = now - state.last_line_at <= 2.0
                    if state.responsive != responsive:
                        state.responsive = responsive
                        self.callback({"type": "health", "role": role, "responsive": responsive})
                    if not responsive:
                        connection = self.roles.get(role)
                        if connection:
                            try:
                                connection.send("INFO")
                                connection.send("STATUS")
                            except serial.SerialException:
                                pass
            self.stop_event.wait(1.5)

    def _event_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                port, line = self.events.get(timeout=0.3)
            except queue.Empty:
                continue
            with self.lock:
                if line == "__PORT_ERROR__":
                    self._remove_port_locked(port)
                    continue
                connection = self.connections.get(port)
                if connection is None:
                    continue

                if line.startswith("INFO"):
                    role = self._identify_role(line)
                    if role:
                        old = self.roles.get(role)
                        if old and old.port_name != port:
                            old.stop()
                            self.connections.pop(old.port_name, None)
                        connection.role = role
                        self.roles[role] = connection
                        values = self._parse_values(line)
                        state = DeviceState(
                            role=role,
                            port=port,
                            connected=True,
                            responsive=True,
                            version=values.get("VERSION", "-"),
                            last_line_at=time.monotonic(),
                        )
                        self.states[role] = state
                        self.callback({"type": "identified", "role": role, "port": port, "line": line})

                role = connection.role
                if role:
                    state = self.states.get(role)
                    if state:
                        state.last_line_at = time.monotonic()
                        state.responsive = True
                    self.callback({"type": "line", "role": role, "port": port, "line": line})

    def _remove_port_locked(self, port: str) -> None:
        connection = self.connections.pop(port, None)
        if connection is None:
            return
        connection.stop()
        if connection.role:
            role = connection.role
            if self.roles.get(role) is connection:
                self.roles.pop(role, None)
            self.states.pop(role, None)
            self.callback({"type": "disconnected", "role": role, "port": port})

    @staticmethod
    def _identify_role(line: str) -> str | None:
        for token, role in ROLE_TOKENS.items():
            if token in line:
                return role
        return None

    @staticmethod
    def _parse_values(line: str) -> dict[str, str]:
        output: dict[str, str] = {}
        for token in line.split()[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                output[key] = value
        return output
