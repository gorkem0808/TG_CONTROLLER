from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .macro import fixed_macro_steps

APP_DIR_NAME = "TG_CONTROLLER_PRO"
DEFAULT_GAME_PATH = r"C:\ArcadeGames\paradiselost\Farcry_R.exe"


def config_dir() -> Path:
    base = Path(os.getenv("APPDATA", Path.home()))
    path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class AppConfig:
    schema: int = 5
    game_path: str = DEFAULT_GAME_PATH
    game_arguments: str = ""
    working_directory: str = r"C:\ArcadeGames\paradiselost"
    macro_delay_seconds: int = 40
    macro_enabled: bool = True
    macro_steps: list[dict[str, Any]] = field(default_factory=list)
    auto_start_game: bool = False
    auto_restart_game: bool = False
    restart_delay_seconds: int = 10
    require_all_devices: bool = True
    start_minimized: bool = True
    windows_autostart: bool = True
    relay_active_low: bool = False
    relay_inactivity_seconds: int = 120
    key_pulse_ms: int = 90
    p1_smoothing: int = 4
    p2_smoothing: int = 4

    def normalize(self) -> None:
        self.schema = 5
        self.macro_enabled = True
        self.macro_steps = fixed_macro_steps()
        self.macro_delay_seconds = max(0, min(999, int(self.macro_delay_seconds)))
        self.restart_delay_seconds = max(1, min(999, int(self.restart_delay_seconds)))
        self.relay_inactivity_seconds = max(0, min(3600, int(self.relay_inactivity_seconds)))
        self.key_pulse_ms = max(20, min(500, int(self.key_pulse_ms)))
        self.p1_smoothing = max(0, min(10, int(self.p1_smoothing)))
        self.p2_smoothing = max(0, min(10, int(self.p2_smoothing)))
        if not self.working_directory and self.game_path:
            self.working_directory = str(Path(self.game_path).parent)


def config_path() -> Path:
    return config_dir() / "settings_v4.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        cfg = AppConfig()
        cfg.normalize()
        return cfg

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        allowed = set(AppConfig.__dataclass_fields__)
        values = {key: value for key, value in raw.items() if key in allowed}
        cfg = AppConfig(**values)
        cfg.normalize()
        return cfg
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        invalid = path.with_suffix(".invalid.json")
        try:
            shutil.copy2(path, invalid)
        except OSError:
            pass
        cfg = AppConfig()
        cfg.normalize()
        return cfg


def save_config(cfg: AppConfig) -> None:
    cfg.normalize()
    path = config_path()
    temp = path.with_suffix(".tmp")
    payload = json.dumps(asdict(cfg), ensure_ascii=False, indent=2)
    temp.write_text(payload, encoding="utf-8")
    os.replace(temp, path)
