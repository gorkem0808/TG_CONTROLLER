from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MacroValidationError(ValueError):
    pass


KEYCODES: dict[str, int] = {
    "A": 0x04, "B": 0x05, "C": 0x06, "D": 0x07, "E": 0x08,
    "F": 0x09, "G": 0x0A, "H": 0x0B, "I": 0x0C, "J": 0x0D,
    "K": 0x0E, "L": 0x0F, "M": 0x10, "N": 0x11, "O": 0x12,
    "P": 0x13, "Q": 0x14, "R": 0x15, "S": 0x16, "T": 0x17,
    "U": 0x18, "V": 0x19, "W": 0x1A, "X": 0x1B, "Y": 0x1C,
    "Z": 0x1D,
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    "ENTER": 0x28, "ESC": 0x29, "BACKSPACE": 0x2A, "TAB": 0x2B,
    "SPACE": 0x2C, "F1": 0x3A, "F2": 0x3B, "F3": 0x3C,
    "F4": 0x3D, "F5": 0x3E, "F6": 0x3F, "F7": 0x40,
    "F8": 0x41, "F9": 0x42, "F10": 0x43, "F11": 0x44,
    "F12": 0x45, "RIGHT": 0x4F, "LEFT": 0x50, "DOWN": 0x51,
    "UP": 0x52, "HOME": 0x4A, "END": 0x4D, "PAGEUP": 0x4B,
    "PAGEDOWN": 0x4E, "DELETE": 0x4C, "INSERT": 0x49,
}


@dataclass(frozen=True)
class CompiledStep:
    keycode: int
    hold_ms: int
    wait_ms: int


def validate_macro(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise MacroValidationError("Makro JSON bir liste olmalıdır.")
    if len(raw) > 32:
        raise MacroValidationError("Makro en fazla 32 adımdan oluşabilir.")

    normalized: list[dict[str, Any]] = []
    total_ms = 0
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise MacroValidationError(f"{index}. adım nesne olmalıdır.")
        step_type = str(item.get("type", "")).lower()
        if step_type == "wait":
            try:
                milliseconds = int(item.get("ms", 0))
            except (TypeError, ValueError) as exc:
                raise MacroValidationError(f"{index}. bekleme süresi sayı olmalıdır.") from exc
            if not 0 <= milliseconds <= 60000:
                raise MacroValidationError(f"{index}. bekleme 0–60000 ms arasında olmalıdır.")
            normalized.append({"type": "wait", "ms": milliseconds})
            total_ms += milliseconds
        elif step_type == "key":
            key = str(item.get("key", "")).upper().strip()
            if key not in KEYCODES:
                raise MacroValidationError(f"{index}. adımda desteklenmeyen tuş: {key!r}")
            try:
                hold_ms = int(item.get("hold_ms", 100))
                wait_ms = int(item.get("wait_ms", 300))
            except (TypeError, ValueError) as exc:
                raise MacroValidationError(f"{index}. tuş süreleri sayı olmalıdır.") from exc
            if not 20 <= hold_ms <= 5000:
                raise MacroValidationError(f"{index}. hold_ms 20–5000 arasında olmalıdır.")
            if not 0 <= wait_ms <= 60000:
                raise MacroValidationError(f"{index}. wait_ms 0–60000 arasında olmalıdır.")
            normalized.append(
                {"type": "key", "key": key, "hold_ms": hold_ms, "wait_ms": wait_ms}
            )
            total_ms += hold_ms + wait_ms
        else:
            raise MacroValidationError(f"{index}. adım type değeri 'key' veya 'wait' olmalıdır.")

    if total_ms > 900000:
        raise MacroValidationError("Makronun toplam süresi 15 dakikayı aşamaz.")
    return normalized


def compile_macro(raw: Any) -> list[CompiledStep]:
    steps = validate_macro(raw)
    compiled: list[CompiledStep] = []
    for step in steps:
        if step["type"] == "wait":
            compiled.append(CompiledStep(0, 0, int(step["ms"])))
        else:
            compiled.append(
                CompiledStep(
                    KEYCODES[str(step["key"])],
                    int(step["hold_ms"]),
                    int(step["wait_ms"]),
                )
            )
    return compiled


def example_macro() -> list[dict[str, Any]]:
    return [
        {"type": "key", "key": "F1", "hold_ms": 100, "wait_ms": 900},
        {"type": "key", "key": "F2", "hold_ms": 100, "wait_ms": 900},
    ]
