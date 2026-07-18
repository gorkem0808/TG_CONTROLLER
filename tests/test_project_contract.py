from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectContractTests(unittest.TestCase):
    def test_controller_contract(self) -> None:
        text = (ROOT / "firmware/controller/main.c").read_text(encoding="utf-8")
        for token in (
            "CALIBRATION_HOLD_MS 10000u",
            "MAINTENANCE_TIMEOUT_MS 180000u",
            "settings.inactivity_s = 120u",
            "relay_awake && buttons[BTN_P1_TRIGGER].stable",
            "relay_awake && buttons[BTN_P2_TRIGGER].stable",
            "HID_KEY_3",
            "HID_KEY_6",
            "MACRO MAX",
        ):
            if token == "MACRO MAX":
                self.assertIn("MACRO_MAX_STEPS 32u", text)
            else:
                self.assertIn(token, text)

    def test_gun_contract(self) -> None:
        text = (ROOT / "firmware/gun/main.c").read_text(encoding="utf-8")
        for token in (
            "GP19_ENABLE_PIN 19u",
            "SOFTWARE_OFF_LEASE_MS 5000u",
            "CALIBRATION_SAMPLES 32u",
            "CALIBRATION_MAX_SPREAD 120u",
            "bilinear_inverse",
            "SETTINGS_SECTOR_A",
            "SETTINGS_SECTOR_B",
        ):
            self.assertIn(token, text)

    def test_no_old_release_names_in_user_facing_files(self) -> None:
        allowed_source = ROOT / "docs" / "EKSIKLER_KAPATMA_RAPORU.md"
        for path in ROOT.rglob("*"):
            if not path.is_file() or path in {allowed_source, Path(__file__).resolve()} or path.suffix in {".zip", ".pyc"}:
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn("Startup_V2", text, str(path))
            self.assertNotIn("MANAGER V2", text, str(path))


    def test_manager_has_no_psutil_runtime_dependency(self) -> None:
        game_text = (ROOT / "desktop/tg_controller/game.py").read_text(encoding="utf-8")
        requirements = (ROOT / "desktop/requirements.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertNotIn("import psutil", game_text)
        self.assertNotIn("psutil==", requirements)
        self.assertIn("--self-test", workflow)
        self.assertIn("TG_CONTROLLER_PRO_MANAGER_V4_2.exe", workflow)


    def test_tray_hotfix_contract(self) -> None:
        tray = (ROOT / "desktop/tg_controller/tray.py").read_text(encoding="utf-8")
        ui = (ROOT / "desktop/tg_controller/ui.py").read_text(encoding="utf-8")
        single = (ROOT / "desktop/tg_controller/single_instance.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn("ready_event", tray)
        self.assertIn("self.tray_available", ui)
        self.assertIn("signal_show_request", single)
        self.assertIn("consume_show_request", single)
        self.assertIn("pystray._win32", workflow)
        self.assertIn("TG_CONTROLLER_PRO_MANAGER_V4_2.exe", workflow)


if __name__ == "__main__":
    unittest.main()
