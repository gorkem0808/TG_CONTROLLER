from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tg_controller.config import AppConfig, DEFAULT_GAME_PATH, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_defaults_match_cabinet_path_and_limits(self) -> None:
        cfg = AppConfig()
        self.assertEqual(cfg.game_path, DEFAULT_GAME_PATH)
        self.assertEqual(cfg.relay_inactivity_seconds, 120)
        self.assertEqual(cfg.macro_delay_seconds, 40)
        self.assertTrue(cfg.windows_autostart)

    def test_normalize_clamps_values(self) -> None:
        cfg = AppConfig(
            macro_delay_seconds=2000,
            relay_inactivity_seconds=-1,
            key_pulse_ms=9999,
            p1_smoothing=-5,
            p2_smoothing=99,
        )
        cfg.normalize()
        self.assertEqual(cfg.macro_delay_seconds, 999)
        self.assertEqual(cfg.relay_inactivity_seconds, 0)
        self.assertEqual(cfg.key_pulse_ms, 500)
        self.assertEqual(cfg.p1_smoothing, 0)
        self.assertEqual(cfg.p2_smoothing, 10)

    def test_atomic_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.dict(os.environ, {"APPDATA": temp}):
                cfg = AppConfig(macro_delay_seconds=350, p1_smoothing=7)
                save_config(cfg)
                loaded = load_config()
                self.assertEqual(loaded.macro_delay_seconds, 350)
                self.assertEqual(loaded.p1_smoothing, 7)
                self.assertTrue((Path(temp) / "TG_CONTROLLER_PRO" / "settings_v4.json").exists())


if __name__ == "__main__":
    unittest.main()
