# profilelab driver contract

A **driver** is an HTTP service that applies profile edits to a target platform. The profilelab container is platform-agnostic — it interacts with whichever driver is reachable at `DRIVER_URL` (default `http://localhost:8765`, pointing at the in-container driver process). Any new platform integration (LinkedIn web, Hinge, Android via ADB, etc.) is a new driver that satisfies this contract.

**v0 reference driver** is `drivers/bumble-web/` — Playwright-based, runs in-container. Earlier designs called for a macOS host agent driving iPhone Mirroring; that path is abandoned (Apple filters synthetic events into iPhone Mirroring — see commit history).

All endpoints accept and return JSON unless otherwise noted.

---

## Health & session

### `GET /health`

Liveness + connection check. Called every 60s by the orchestrator.

**Response** (`200 OK`):
```json
{
  "ok": true,
  "connected": true,
  "session_age_s": 4321,
  "driver": "macos-iphone-mirroring",
  "version": "0.0.1"
}
```

- `connected` is `false` if the driver can see the app surface is not currently available (e.g., iPhone Mirroring window closed). On `connected=false` the orchestrator **pauses the experiment window clock** — dead time does not count as signal.

### `POST /reconnect`

Ask the driver to re-establish whatever session it needs (e.g., relaunch iPhone Mirroring, re-auth).

**Response** (`200 OK`):
```json
{ "ok": true, "connected": true }
```

---

## Profile edits

Every edit endpoint is **idempotent** from the orchestrator's perspective: the driver ensures the on-device state matches the request, then self-verifies via screenshot diff against the submitted spec. If verification fails after one retry, the driver returns `verified: false` and the orchestrator treats the experiment as `status=apply_failed` (no window opens, no score computed).

### `POST /flow/edit_photo`

Replace the photo in slot N with the image at `source_path` (absolute path on the driver host — photos are shared via bind mount or fetched by the driver from a file-server URL, driver's choice).

**Request**:
```json
{ "slot": 1, "source_path": "/Users/you/profilelab/state/photos/p42.jpg" }
```

`slot` is 1-indexed. Maximum slot = 6 for Bumble v0.

**Response** (`200 OK`):
```json
{ "ok": true, "verified": true }
```

### `POST /flow/edit_prompt`

Update the text of prompt N (Bumble prompts are positional).

**Request**:
```json
{ "slot": 2, "text": "My most controversial opinion is..." }
```

**Response**: same shape as `edit_photo`.

### `POST /flow/edit_bio`

Replace the "About me" text.

**Request**:
```json
{ "text": "..." }
```

**Response**: same shape as `edit_photo`.

### `POST /flow/save_profile`

Commit any pending draft edits on the target app. Called at the end of a batch of edits.

**Request**: `{}`

**Response**:
```json
{ "ok": true, "verified": true }
```

---

## Metrics

### `GET /metrics`

Return the current engagement counters visible on the platform. Must not require any UI state beyond "app is open."

**Response** (`200 OK`):
```json
{
  "ts": "2026-04-17T10:30:00Z",
  "likes": 17,
  "matches": 4,
  "confidence": 0.95
}
```

- `ts` is the driver-side timestamp at the moment of read (ISO 8601, UTC).
- `confidence` is the vision/OCR pipeline's self-reported confidence. < 0.5 reads are logged but excluded from scoring.
- If the driver cannot read a metric (e.g., Bumble is showing a paywall modal), it returns `null` for that field and `confidence: 0.0`. The orchestrator skips that sample.

Additional metrics (e.g., `reply_rate`, `unread_messages`) may be added via additive optional fields. Consumers must tolerate unknown fields.

---

## Screenshots

### `GET /screenshot`

Debug/audit endpoint. Returns a PNG of the current app surface.

**Query params**:
- `region` (optional): `x,y,w,h` in driver pixels. Default is full app region.

**Response** (`200 OK`, `Content-Type: image/png`): raw PNG bytes.

Not on the hot path — used by the orchestrator's approval UI and for post-hoc audit when scoring looks anomalous.

---

## Errors

Drivers must return structured errors:

```json
{ "error": "apply_failed", "detail": "photo slot 1 did not change after 2 attempts" }
```

HTTP status conventions:
- `200` — success
- `400` — malformed request
- `409` — transient state conflict (e.g., Bumble is showing a modal the driver cannot dismiss)
- `502` — platform-side failure (e.g., iPhone Mirroring disconnected mid-flow)
- `503` — driver not yet ready (session still initializing)

The orchestrator retries `502`/`503` with backoff and pauses the window clock while retrying.

---

## Authoring a new driver

1. Implement the endpoints above in any language/framework. Recommended: FastAPI for Python drivers, matching the v0 reference driver structure in `drivers/macos-iphone-mirroring/`.
2. Expose on a port of your choosing; set `DRIVER_URL` in the container's `.env`.
3. Add verification logic: after every `POST /flow/*`, re-read the on-device state and compare to the requested spec before returning `verified: true`.
4. Add reconnection logic that handles your platform's session timeouts.
5. Submit a PR with a new `drivers/<name>/` subproject; include a README describing platform-specific setup (permissions, cabling, pairing, etc.).

The container has no platform-specific code. If your driver correctly implements this contract, the existing orchestrator + pi setup will drive it.
