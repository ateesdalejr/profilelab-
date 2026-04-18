# profilelab — Bumble Web driver

v0 driver implementing the profilelab driver contract (see `../../docs/drivers.md`). Drives [Bumble Web](https://bumble.com/app) via Playwright running inside the container.

This driver runs entirely in-container — no macOS host agent, no iPhone hardware. The whole system is cross-platform.

## Setup

```sh
uv sync
uv run playwright install chromium     # one-time, ~150 MB
uv run pyright
uv run ruff check .
```

## M0 probe

Before building any real flows, verify Playwright can load Bumble Web without hitting a bot-detection wall:

```sh
uv run python -m profilelab_driver.probe            # headless
uv run python -m profilelab_driver.probe --headed   # visible browser — useful if headless gets blocked
```

The probe loads `https://bumble.com/app`, captures a full-page screenshot to `./probe_output/bumble-load.png`, and reports one of:

- **GO** — page loaded cleanly, login UI reachable. M1 proceeds.
- **SOFT-BLOCK** — hit a Cloudflare/Datadome/captcha challenge. Next moves, in order: `--headed`, persistent user-data-dir, `playwright-stealth`, residential proxy.
- **NO-GO** — Playwright couldn't even load the page.

## Authentication (later)

Bumble Web uses phone + SMS verification. Automating SMS is out of scope and likely against ToS. The operational plan: you log in manually **once** in a persistent Playwright profile (user-data-dir), the driver reuses the saved cookies/storage for subsequent runs, and re-alerts you only if the session expires.

## Dev commands

```sh
uv run profilelab-driver        # start FastAPI driver on :8765
uv run profilelab-driver-probe  # run M0 probe
uv run pyright                  # typecheck
uv run ruff check .             # lint
uv run ruff format .            # format
```
