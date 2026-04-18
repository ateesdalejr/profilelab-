"""M0 de-risking probe for the Bumble Web driver.

Question this probe answers: can Playwright load Bumble Web at all,
without hitting a bot-detection wall (Cloudflare challenge, Datadome,
captcha, etc.)? If the page loads and the login UI is reachable, M1
(real Playwright-driven profile edits) is viable. If we hit a challenge
wall, the pivot is another level deeper (residential proxy, real user
data dir, playwright-stealth, etc.).

Usage:
    uv run python -m profilelab_driver.probe            # headless
    uv run python -m profilelab_driver.probe --headed   # visible browser

First run: you need a browser binary. `uv run playwright install chromium`.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BUMBLE_URL = "https://bumble.com/app"
_DEFAULT_OUTPUT_DIR = Path.cwd() / "probe_output"
_PAGE_LOAD_TIMEOUT_MS = 30_000

_BOT_WALL_MARKERS = (
    "just a moment",
    "checking your browser",
    "cloudflare",
    "please verify you are human",
    "unable to verify",
    "access denied",
    "ddos protection",
    "you have been blocked",
)
# Note: "captcha" alone is not a wall marker — hCaptcha libs preload on
# many legit login pages without challenging the user. A real wall would
# match one of the phrases above.

_LOGIN_MARKERS = (
    "sign in",
    "continue with",
    "phone number",
    "verify your",
    "get started",
)


@dataclass(frozen=True)
class ProbeResult:
    loaded: bool
    final_url: str
    page_title: str
    bot_wall_detected: bool
    detection_markers: tuple[str, ...] = field(default_factory=tuple)
    login_ui_visible: bool = False
    screenshot: Path | None = None
    error: str | None = None

    def verdict(self) -> str:
        if self.error:
            return f"NO-GO — probe errored before reaching the page: {self.error}"
        if not self.loaded:
            return "NO-GO — page did not load within timeout."
        # Login UI outranks weak bot-wall signals: if we can see the login
        # form, we are through regardless of preloaded captcha scripts.
        if self.login_ui_visible and not self.bot_wall_detected:
            return "GO — page loaded cleanly and the login UI is reachable. M1 proceeds."
        if self.bot_wall_detected:
            markers = ", ".join(self.detection_markers)
            return (
                f"SOFT-BLOCK — page loaded but hit a bot challenge ({markers}). "
                "Next step: try --headed, then a persistent user-data-dir, then "
                "playwright-stealth, then a residential proxy if all else fails."
            )
        return (
            "UNCLEAR — page loaded but no login UI markers were found. "
            "Open the screenshot and inspect manually before deciding."
        )


def _detect_bot_wall(html_lower: str) -> tuple[str, ...]:
    return tuple(m for m in _BOT_WALL_MARKERS if m in html_lower)


def _detect_login_ui(html_lower: str) -> bool:
    return any(m in html_lower for m in _LOGIN_MARKERS)


def run(output_dir: Path = _DEFAULT_OUTPUT_DIR, headed: bool = False) -> ProbeResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "bumble-load.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            # Timeout isn't fatal — a challenge page may still be rendered.
            with contextlib.suppress(PlaywrightTimeoutError):
                page.goto(BUMBLE_URL, wait_until="networkidle", timeout=_PAGE_LOAD_TIMEOUT_MS)

            final_url = page.url
            title = page.title()
            html_lower = page.content().lower()
            page.screenshot(path=str(screenshot_path), full_page=True)

            browser.close()

            markers = _detect_bot_wall(html_lower)
            return ProbeResult(
                loaded=True,
                final_url=final_url,
                page_title=title,
                bot_wall_detected=bool(markers),
                detection_markers=markers,
                login_ui_visible=_detect_login_ui(html_lower),
                screenshot=screenshot_path,
            )
    except Exception as exc:  # probe reports any failure to the user
        return ProbeResult(
            loaded=False,
            final_url="",
            page_title="",
            bot_wall_detected=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bumble Web M0 probe")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser visible (defaults to headless)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory for probe artifacts (default: ./probe_output)",
    )
    args = parser.parse_args()

    print(f"Loading {BUMBLE_URL} via Playwright ({'headed' if args.headed else 'headless'})...")
    print("(First run requires `uv run playwright install chromium` — ~150 MB.)")

    result = run(output_dir=args.out, headed=args.headed)

    print()
    print(f"loaded:        {result.loaded}")
    print(f"final_url:     {result.final_url or '(none)'}")
    print(f"page_title:    {result.page_title or '(none)'}")
    print(f"bot_wall:      {result.bot_wall_detected}")
    if result.detection_markers:
        print(f"  markers:     {', '.join(result.detection_markers)}")
    print(f"login_ui:      {result.login_ui_visible}")
    if result.screenshot is not None:
        print(f"screenshot:    {result.screenshot.resolve()}")
    if result.error:
        print(f"error:         {result.error}", file=sys.stderr)
    print()
    print(result.verdict())

    return 0 if (result.loaded and not result.bot_wall_detected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
