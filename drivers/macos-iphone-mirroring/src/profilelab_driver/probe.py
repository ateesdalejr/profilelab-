"""M0 de-risking probe.

Before building any more driver code, verify that synthetic mouse events
actually reach the iPhone Mirroring window. macOS grants applications
event-synthesis access via Accessibility permissions; iPhone Mirroring
also gates some events at a lower level.

Usage:
    uv run python -m profilelab_driver.probe <x> <y>

The probe clicks at (x, y) using cliclick, waits for user input, then
clicks again using pynput, and asks the user which (if any) landed.
The outcome decides the whole project's driver strategy (see PLAN.md M0).
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Literal

from pynput.mouse import Button, Controller

Outcome = Literal["landed", "missed", "unclear"]


@dataclass(frozen=True)
class ProbeResult:
    cliclick: Outcome
    pynput: Outcome

    def verdict(self) -> str:
        if self.cliclick == "landed" or self.pynput == "landed":
            winners = [
                name
                for name, outcome in (("cliclick", self.cliclick), ("pynput", self.pynput))
                if outcome == "landed"
            ]
            return f"GO — {'+'.join(winners)} can drive iPhone Mirroring."
        if self.cliclick == "missed" and self.pynput == "missed":
            return (
                "NO-GO — neither input path landed events. "
                "Pivot to wired Android + ADB, libimobiledevice, or HID dongle "
                "before writing more driver code."
            )
        return (
            "UNCLEAR — re-run the probe after focusing iPhone Mirroring and "
            "granting accessibility permissions to Terminal (or your shell's host app) "
            "in System Settings → Privacy & Security → Accessibility."
        )


def _prompt_outcome(name: str) -> Outcome:
    while True:
        raw = input(f"Did the {name} click land in iPhone Mirroring? [y/n/?]: ").strip().lower()
        match raw:
            case "y" | "yes":
                return "landed"
            case "n" | "no":
                return "missed"
            case "?" | "u" | "unclear" | "":
                return "unclear"
            case _:
                print("Please answer y, n, or ?")


def _click_via_cliclick(x: int, y: int) -> bool:
    try:
        subprocess.run(
            ["cliclick", f"c:{x},{y}"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError:
        print("  cliclick not installed — `brew install cliclick`")
        return False
    except subprocess.CalledProcessError as exc:
        print(f"  cliclick errored: {exc.stderr.decode(errors='replace').strip()}")
        return False
    except subprocess.TimeoutExpired:
        print("  cliclick timed out")
        return False
    return True


def _click_via_pynput(x: int, y: int) -> bool:
    try:
        mouse = Controller()
        mouse.position = (x, y)
        time.sleep(0.05)
        mouse.click(Button.left, 1)
    except Exception as exc:  # pynput surfaces platform errors broadly
        print(f"  pynput errored: {exc!r}")
        return False
    return True


def run(x: int, y: int) -> ProbeResult:
    print(f"Probing click at ({x}, {y}). Focus iPhone Mirroring with Bumble open first.")
    print("You have 3 seconds to switch windows...")
    time.sleep(3)

    print("\n[1/2] cliclick...")
    cliclick_invoked = _click_via_cliclick(x, y)
    cliclick_outcome: Outcome = _prompt_outcome("cliclick") if cliclick_invoked else "missed"

    print("\n[2/2] pynput...")
    print("You have 3 seconds to refocus iPhone Mirroring if it lost focus...")
    time.sleep(3)
    pynput_invoked = _click_via_pynput(x, y)
    pynput_outcome: Outcome = _prompt_outcome("pynput") if pynput_invoked else "missed"

    return ProbeResult(cliclick=cliclick_outcome, pynput=pynput_outcome)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <x> <y>", file=sys.stderr)
        return 2
    try:
        x = int(sys.argv[1])
        y = int(sys.argv[2])
    except ValueError:
        print("x and y must be integers", file=sys.stderr)
        return 2

    result = run(x, y)
    print()
    print(f"cliclick: {result.cliclick}")
    print(f"pynput:   {result.pynput}")
    print()
    print(result.verdict())
    return 0 if result.cliclick == "landed" or result.pynput == "landed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
