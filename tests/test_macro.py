from __future__ import annotations

import unittest

from tg_controller.macro import (
    FIXED_MACRO_DIGITS,
    MacroValidationError,
    compile_macro,
    fixed_macro_steps,
    validate_macro,
)


class MacroTests(unittest.TestCase):
    def test_compiles_key_and_wait(self) -> None:
        compiled = compile_macro(
            [
                {"type": "key", "key": "3", "hold_ms": 100, "wait_ms": 300},
                {"type": "wait", "ms": 750},
            ]
        )
        self.assertEqual(compiled[0].keycode, 0x20)
        self.assertEqual(compiled[0].hold_ms, 100)
        self.assertEqual(compiled[0].wait_ms, 300)
        self.assertEqual(compiled[1].keycode, 0)
        self.assertEqual(compiled[1].wait_ms, 750)

    def test_rejects_unknown_key(self) -> None:
        with self.assertRaises(MacroValidationError):
            validate_macro([{"type": "key", "key": "NOT_A_KEY"}])

    def test_rejects_too_many_steps(self) -> None:
        with self.assertRaises(MacroValidationError):
            validate_macro([{"type": "wait", "ms": 1}] * 33)

    def test_rejects_macro_longer_than_fifteen_minutes(self) -> None:
        with self.assertRaises(MacroValidationError):
            validate_macro([{"type": "wait", "ms": 60000}] * 16)


    def test_fixed_macro_is_exact(self) -> None:
        self.assertEqual(
            FIXED_MACRO_DIGITS,
            "345455535455535455335555555544",
        )
        steps = fixed_macro_steps()
        self.assertEqual(len(steps), 30)
        expected = {"3": "3", "4": "4", "5": "5"}
        self.assertEqual(
            [step["key"] for step in steps],
            [expected[digit] for digit in FIXED_MACRO_DIGITS],
        )


if __name__ == "__main__":
    unittest.main()
