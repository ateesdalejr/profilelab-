"""M0 de-risking probe.

Before building any more driver code, verify that synthetic mouse events
actually reach the iPhone Mirroring window. macOS grants applications
event-synthesis access via Accessibility permissions; iPhone Mirroring
also gates some events at a lower level.

Usage:
    uv run python -m profilelab_driver.probe

The probe starts a countdown during which you:
  1. Switch to iPhone Mirroring (Cmd+Tab).
  2. Position your cursor over a safe target in Bumble (not a swipe
     button; somewhere empty like the feed background or your own
     profile header).
  3. Hold still.

At T-0 the probe captures the cursor position, fires a cliclick there,
waits, then fires a pynput click at the same spot. Screenshots are
saved to ``./probe_output/`` (before, after cliclick, after pynput) so
you can review which clicks landed without having to watch live.

Afterward, switch back to the terminal and answer the y/n prompts based
on what the screenshots show. The verdict (GO / NO-GO / UNCLEAR) decides
whether the rest of the macOS driver plan holds (see PLAN.md M0).
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import mss
import mss.tools
from pynput.mouse import Button, Controller

Outcome = Literal["landed", "missed", "unclear"]

_COUNTDOWN_SECONDS = 10
_CLICK_GAP_SECONDS = 2.0
_POST_CLICK_SETTLE_SECONDS = 0.6
_DEFAULT_OUTPUT_DIR = Path.cwd() / "probe_output"


@dataclass(frozen=True)
class ProbeResult:
    cliclick: Outcome
    pynput: Outcome
    screenshots: Path

    def verdict(self) -> str:
        landed = [
            name
            for name, outcome in (("cliclick", self.cliclick), ("pynput", self.pynput))
            if outcome == "landed"
        ]
        if landed:
            return f"GO — {'+'.join(landed)} can drive iPhone Mirroring."
        if self.cliclick == "missed" and self.pynput == "missed":
            return (
                "NO-GO — neither input path landed events. "
                "Pivot to wired Android + ADB, libimobiledevice, or HID dongle "
                "before writing more driver code."
            )
        return (
            "UNCLEAR — re-run the probe. If it stays unclear, likely Accessibility "
            "permissions: System Settings → Privacy & Security → Accessibility → "
            "add your terminal (Terminal/iTerm/Ghostty)."
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
                print("  Please answer y, n, or ?")


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


def _save_full_screenshot(path: Path) -> None:
    with mss.mss() as sct:
        # monitors[0] is the virtual union of all displays, monitors[1] is the primary.
        shot = sct.grab(sct.monitors[1])
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))


def _countdown(seconds: int) -> None:
    for i in range(seconds, 0, -1):
        sys.stdout.write(f"\r  T-{i:>2}s — position cursor over target in iPhone Mirroring... ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r  T- 0s — firing now.                                      \n")
    sys.stdout.flush()


def run(output_dir: Path = _DEFAULT_OUTPUT_DIR) -> ProbeResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Probe: iPhone Mirroring click delivery")
    print("--------------------------------------")
    print("1. Open iPhone Mirroring and bring Bumble to a safe area (no swipe buttons;")
    print("   the feed background, your own profile, or a prompt-edit screen is fine).")
    print("2. When the countdown ends, your cursor position will be captured and clicks")
    print("   will fire there. Before T-0: Cmd+Tab to iPhone Mirroring, move the cursor")
    print("   to the target, and hold still.")
    print("3. Screenshots (before / after cliclick / after pynput) land in:")
    print(f"     {output_dir.resolve()}/")
    print("4. After the clicks fire, switch back to this terminal to answer y/n")
    print("   based on what the screenshots show.")
    print()
    input("Press Enter to start the countdown... ")
    print()

    _countdown(_COUNTDOWN_SECONDS)

    mouse = Controller()
    cursor_x, cursor_y = mouse.position
    x, y = int(cursor_x), int(cursor_y)
    print(f"  Target locked at ({x}, {y})")

    before_path = output_dir / "1-before.png"
    _save_full_screenshot(before_path)

    cliclick_invoked = _click_via_cliclick(x, y)
    time.sleep(_POST_CLICK_SETTLE_SECONDS)
    after_cliclick_path = output_dir / "2-after-cliclick.png"
    _save_full_screenshot(after_cliclick_path)

    time.sleep(_CLICK_GAP_SECONDS)

    pynput_invoked = _click_via_pynput(x, y)
    time.sleep(_POST_CLICK_SETTLE_SECONDS)
    after_pynput_path = output_dir / "3-after-pynput.png"
    _save_full_screenshot(after_pynput_path)

    print()
    print("Screenshots saved:")
    print(f"  {before_path.name}          — state before any click")
    print(f"  {after_cliclick_path.name} — state after cliclick fired")
    print(f"  {after_pynput_path.name}   — state after pynput fired")
    print()
    print("Open them (QuickLook: spacebar in Finder) and compare:")
    print("  - If 2 differs from 1 at the click point: cliclick landed.")
    print("  - If 3 differs from 2 at the click point: pynput landed.")
    print()

    cliclick_outcome: Outcome = _prompt_outcome("cliclick") if cliclick_invoked else "missed"
    pynput_outcome: Outcome = _prompt_outcome("pynput") if pynput_invoked else "missed"

    return ProbeResult(
        cliclick=cliclick_outcome,
        pynput=pynput_outcome,
        screenshots=output_dir,
    )


def main() -> int:
    result = run()
    print()
    print(f"cliclick: {result.cliclick}")
    print(f"pynput:   {result.pynput}")
    print(f"shots:    {result.screenshots.resolve()}")
    print()
    print(result.verdict())
    return 0 if result.cliclick == "landed" or result.pynput == "landed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
