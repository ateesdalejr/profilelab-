"""iPhone Mirroring session detection for macOS.

The driver needs to know whether the iPhone Mirroring window is
currently live so `/health` can report `connected` honestly and
`/reconnect` can be a no-op when nothing's wrong. We deliberately
shell out to osascript rather than link PyObjC directly — it's
zero-setup, predictable, and easy to read.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

_PROCESS_CHECK_SCRIPT = (
    'tell application "System Events" to (name of processes) contains "iPhone Mirroring"'
)


@dataclass
class SessionState:
    """Best-effort snapshot of the driver's control surface."""

    connected: bool
    first_seen_at: float
    last_checked_at: float

    @property
    def session_age_s(self) -> int:
        if not self.connected:
            return 0
        return max(0, int(self.last_checked_at - self.first_seen_at))


class SessionTracker:
    """Polls iPhone Mirroring presence and tracks session lifetime."""

    def __init__(self) -> None:
        now = time.monotonic()
        self._state = SessionState(connected=False, first_seen_at=now, last_checked_at=now)

    def refresh(self) -> SessionState:
        """Re-check the system and update the tracked state."""
        now = time.monotonic()
        connected = _is_iphone_mirroring_running()
        if connected and not self._state.connected:
            # Session just came back up — reset the age counter.
            self._state = SessionState(
                connected=True,
                first_seen_at=now,
                last_checked_at=now,
            )
        else:
            self._state = SessionState(
                connected=connected,
                first_seen_at=self._state.first_seen_at,
                last_checked_at=now,
            )
        return self._state

    @property
    def state(self) -> SessionState:
        return self._state


def _is_iphone_mirroring_running() -> bool:
    try:
        result = subprocess.run(
            ["osascript", "-e", _PROCESS_CHECK_SCRIPT],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"
