# profilelab — macOS iPhone Mirroring driver

v0 driver implementing the profilelab driver contract (see `../../docs/drivers.md`). Drives the Bumble app inside the macOS Sequoia iPhone Mirroring window using `cliclick`/`pynput` for input and `mss` for screen capture.

## M0 probe

Before building anything else, verify that synthetic events actually land in iPhone Mirroring.

1. Open iPhone Mirroring on macOS and bring Bumble to a **safe area** — no swipe buttons in range. Good targets: your own profile header, a prompt-edit screen, the empty area below the feed.
2. Kick off the probe from this directory:
   ```sh
   uv run python -m profilelab_driver.probe
   ```
3. Press Enter to start the 10-second countdown. During the countdown, Cmd+Tab to iPhone Mirroring and position your cursor over the target. Hold still.
4. At T-0 the probe captures the cursor position, fires a `cliclick`, waits, then fires a `pynput` click at the same spot. Three full-screen screenshots (before / after-cliclick / after-pynput) land in `./probe_output/`.
5. Switch back to the terminal. Open the three PNGs in QuickLook (spacebar in Finder) and compare. Answer the y/n prompts based on what each transition shows.

Outcomes:
- **GO** — at least one input path landed. M1 (record-replay flows) proceeds.
- **NO-GO** — neither landed. Pivot to wired Android + ADB or libimobiledevice before more driver code.
- **UNCLEAR** — typically an Accessibility permission issue. Grant your terminal (Terminal/iTerm/Ghostty) access in System Settings → Privacy & Security → Accessibility and re-run.

## Setup

```sh
uv sync
uv run pyright
uv run ruff check .
```
