# profilelab — macOS iPhone Mirroring driver

v0 driver implementing the profilelab driver contract (see `../../docs/drivers.md`). Drives the Bumble app inside the macOS Sequoia iPhone Mirroring window using `cliclick`/`pynput` for input and `mss` for screen capture.

## M0 probe

Before building anything else, verify that synthetic events actually land in iPhone Mirroring:

1. Open iPhone Mirroring on macOS, focus Bumble.
2. Move a harmless target into view (e.g., Bumble's main feed — not a profile you'd accidentally swipe).
3. Run the probe:
   ```sh
   uv run python -m profilelab_driver.probe <x> <y>
   ```
4. Report whether the `cliclick` click landed, the `pynput` click landed, or neither.

If neither lands, the macOS iPhone Mirroring path is dead and the project needs a different driver strategy (wired Android + ADB, libimobiledevice, or HID dongle) before any further driver work.

## Setup

```sh
uv sync
uv run pyright
uv run ruff check .
```
