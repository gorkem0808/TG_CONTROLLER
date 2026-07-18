from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "Controller 10 sn kalibrasyon kısayolu": ("firmware/controller/main.c", "CALIBRATION_HOLD_MS 10000u"),
    "Controller 2 dk röle uykusu": ("firmware/controller/main.c", "settings.inactivity_s = 120u"),
    "Röle tetik basılı sürece": ("firmware/controller/main.c", "const bool relay1_active ="),
    "Tetik HID basılı sürece": ("firmware/controller/main.c", "buttons[BTN_P1_TRIGGER].stable"),
    "Bakım modu": ("firmware/controller/main.c", "maintenance_mode"),
    "GP2 10 sn makro": ("firmware/controller/main.c", "coin_long_latched"),
    "GP19 P1/P2": ("firmware/gun/main.c", "GP19_ENABLE_PIN 19u"),
    "32 örnek kalibrasyon": ("firmware/gun/main.c", "CALIBRATION_SAMPLES 32u"),
    "Kararsız köşe reddi": ("firmware/gun/main.c", "EVENT CALUNSTABLE"),
    "Gerçek dört köşe dönüşümü": ("firmware/gun/main.c", "bilinear_inverse"),
    "Çift sektör flash": ("firmware/gun/main.c", "SETTINGS_SECTOR_B"),
    "Global F8": ("desktop/tg_controller/ui.py", "RegisterHotKey"),
    "Sistem tepsisi": ("desktop/tg_controller/tray.py", "pystray"),
    "Tek örnek kilidi": ("desktop/tg_controller/single_instance.py", "CreateMutexW"),
    "Otomatik COM tanıma": ("desktop/tg_controller/device_manager.py", "ROLE_TOKENS"),
    "0–999 makro bekleme": ("desktop/tg_controller/config.py", "min(999"),
    "Varsayılan Paradise Lost yolu": ("desktop/tg_controller/config.py", r"C:\ArcadeGames\paradiselost\Farcry_R.exe"),
    "psutil bağımlılığı kaldırıldı": ("desktop/tg_controller/game.py", "_windows_process_names"),
    "Paketlenmiş EXE self-test": (".github/workflows/build.yml", "--self-test"),
    "Sabit 30 adım makro": ("firmware/controller/main.c", "345455535455535455335555555544"),
    "GP9 anında makro": ("firmware/controller/main.c", "PIN_MANUAL_MACRO 9u"),
    "Açılış buton kilidi": ("firmware/controller/main.c", "ACCESS_WAIT_MACRO"),
    "Makro sonrası kredi kilidi": ("firmware/controller/main.c", "ACCESS_WAIT_CREDIT"),
    "Kredi sonrası buton açma": ("firmware/controller/main.c", "EVENT BUTTONS UNLOCKED"),
    "Makro düzenlemesi engelli": ("firmware/controller/main.c", "ERR MACRO FIXED"),
}


def main() -> int:
    results: dict[str, str] = {}
    failed = False
    for name, (relative, needle) in CHECKS.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        ok = needle in text
        results[name] = "OK" if ok else "HATA"
        failed |= not ok
        print(f"{results[name]}: {name}")
    (ROOT / "STATIC_VALIDATION.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
