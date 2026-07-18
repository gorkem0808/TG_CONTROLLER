from __future__ import annotations

import argparse
from pathlib import Path


RP2040_FLASH_BYTES = 2 * 1024 * 1024
RESERVED_SETTINGS_BYTES = 2 * 4096
MAX_PROGRAM_BYTES = RP2040_FLASH_BYTES - RESERVED_SETTINGS_BYTES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for path in args.files:
        size = path.stat().st_size
        state = "OK" if size <= MAX_PROGRAM_BYTES else "HATA"
        print(f"{state}: {path} = {size} bayt; sınır = {MAX_PROGRAM_BYTES} bayt")
        failed |= size > MAX_PROGRAM_BYTES
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
