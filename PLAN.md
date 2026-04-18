# profilelab v0 — Execution Plan

## Context

profilelab is an autonomous experiment-loop app that iteratively edits a Bumble profile and optimizes it against **real match/engagement metrics** (not an LLM-as-judge proxy). The optimization loop is [`pi-autoresearch`](https://github.com/davebcn87/pi-autoresearch) — an extension for the `pi` CLI agent that treats optimization as `edit → benchmark → keep-or-revert → repeat`.

The hard constraint driving the architecture: **days-per-experiment cadence** (each variant needs a 72h real-world window to observe matches/likes). Standard pi-autoresearch assumes seconds-scale benchmarks, so the system has to park pi between experiments, collect metrics out-of-band, and resume pi with the score via pi-autoresearch's built-in session-resume mechanism (`autoresearch.md` + `autoresearch.jsonl`).

Second hard constraint: **cross-platform reproducibility**. The project should build and run for anyone — not just macOS users. That forces a driver abstraction: the pi+orchestrator "brain" is in a single portable container; the phone-control "driver" is pluggable. v0 ships a macOS driver (iPhone Mirroring + `cliclick`/`pynput`); future drivers (Android+ADB, etc.) implement the same HTTP contract.

Third constraint: **profile edits only, no automated swipes** (Bumble ToS).

## Architecture

```
┌─────────────────────────────────────────┐       ┌────────────────────────────┐
│ Container (portable, Docker)            │       │ Driver (per-platform, host) │
│                                         │       │                            │
│ ┌─────────────────────────────────────┐ │       │ ┌────────────────────────┐ │
│ │ pi + pi-autoresearch                │ │       │ │ FastAPI service        │ │
│ │   autoresearch.sh (no blocking)     │ │       │ │                        │ │
│ │   writes variant spec to state/     │ │       │ │ macOS v0:              │ │
│ │   calls `bumble` CLI via shell      │ │       │ │  - iPhone Mirroring    │ │
│ └─────────────────────────────────────┘ │◄─────►│ │  - cliclick/pynput     │ │
│                                         │ HTTP  │ │  - screencapture/mss   │ │
│ ┌─────────────────────────────────────┐ │       │ │  - vision LLM for OCR  │ │
│ │ orchestrator (Python daemon)        │ │       │ │                        │ │
│ │  APScheduler: 72h windows           │ │       │ │ Record-replay JSON     │ │
│ │  metrics poller → state/metrics.db  │ │       │ │ flows                  │ │
│ │  scoring.py → pending/exp-N.score   │ │       │ └────────────────────────┘ │
│ │  variant queue + approval gate      │ │       │                            │
│ │  pi supervisor (kill / relaunch)    │ │       │  launchd, caffeinated      │
│ │  Telegram bot (approval + status)   │ │       │  reconnect-on-drop logic   │
│ └─────────────────────────────────────┘ │       │                            │
└─────────────────────────────────────────┘       └────────────────────────────┘
                    │
                    │  bind-mounted
                    ▼
        state/   (git-tracked specs, SQLite, pending/, variants/)
```

### Driver contract

The HTTP contract is the portability surface. Stable endpoints (full spec in `docs/drivers.md`):

```
POST /flow/edit_photo          { slot: int, source_path: str } → { ok, verified }
POST /flow/edit_prompt         { slot: int, text: str }        → { ok, verified }
POST /flow/edit_bio            { text: str }                   → { ok, verified }
POST /flow/save_profile        {}                              → { ok, verified }
GET  /metrics                                                   → { likes, matches, ts }
GET  /screenshot?region=...                                     → PNG
GET  /health                                                    → { ok, connected, session_age_s }
POST /reconnect                                                 → { ok }
```

A Linux user implementing an Android-ADB driver writes their own FastAPI exposing the same endpoints. The container is unaware of the platform.

### Per-experiment flow (pi is disposable)

1. pi writes `state/variants/exp-N.yaml` (the spec) + a proposal marker.
2. Orchestrator sees proposal → sends Telegram approve/reject → on approve, calls driver flows to apply. On failure or reject, writes `score=null, status=skipped`, moves on.
3. `verify_applied`: driver re-screenshots profile, vision LLM confirms spec matches. If mismatch → retry once, else mark failed, move on.
4. Window starts. `variant_live_at` recorded. Orchestrator kills pi.
5. Every 3h, orchestrator polls driver `GET /metrics` → appends to `state/metrics.db`. Heartbeat on `/health`; consecutive failures pause the clock (don't count dead time as signal).
6. At `variant_live_at + 72h`, orchestrator computes score from the metrics window → writes `state/pending/exp-N.score`.
7. Orchestrator launches pi via `pi /autoresearch "exp-N score ready, continue"`. pi reads `autoresearch.md` + jsonl, sees exp-N pending, re-runs `autoresearch.sh` which now reads the score file and emits `METRIC engagement=<n>`. pi runs its keep/revert logic.
8. On revert, orchestrator calls driver flows to re-apply the `baseline` spec from `state/live_profile.json`. `verify_applied` again before continuing.
9. pi proposes next variant; loop.

**pi is disposable.** It exits after each experiment. Supervisor relaunches it on cue from the orchestrator. `autoresearch.md` + `autoresearch.jsonl` are the durable state; everything else in pi's runtime is recoverable from those two files.

### State layout (`state/` — bind-mounted, partly git-tracked)

```
state/
├── autoresearch.md           # pi-autoresearch session doc (committed)
├── autoresearch.jsonl        # pi-autoresearch run log (gitignored, large/churn)
├── autoresearch.sh           # benchmark: reads pending/exp-N.score, emits METRIC (committed)
├── live_profile.json         # ground truth of what's currently on Bumble (committed)
├── variants/
│   ├── baseline.yaml         # initial profile spec (committed)
│   └── exp-N.yaml            # immutable per-experiment specs (committed)
├── proposals/
│   └── exp-N.yaml            # pi-proposed variants awaiting approval (committed)
├── pending/                  # orchestrator → pi handoff (gitignored)
│   └── exp-N.score
├── metrics.db                # SQLite (gitignored)
└── photos/                   # source photo pool (gitignored — personal)
```

## Key decisions

- **Container holds pi + orchestrator.** Portable across Linux/Mac/Windows-with-Docker.
- **Driver is host-native, contract-driven.** v0 is macOS + iPhone Mirroring; Linux/Android drivers can plug in later.
- **pi is disposable between experiments.** No 72h-blocking benchmark; orchestrator kills and resumes pi via `/autoresearch <text>` once the score file lands.
- **State is spec-based, not git-branch-based.** `state/live_profile.json` is source of truth; variants are immutable YAML specs; git commits the state dir for audit only.
- **`verify_applied` gates the window.** Re-screenshot + vision-LLM compare to spec. Window timer does not start until apply is verified. Failed applies are marked, not measured.
- **`bumble` CLI, not MCP.** pi learns it via a pi skill. MCP wrapper can be added later if a non-pi agent ever needs it.
- **Approval via Telegram.** `python-telegram-bot` with inline Approve/Reject buttons. Orchestrator owns the bot; pi never blocks on approval — proposals queue and pi moves on until next cycle.
- **Window length: 72h, configurable** via `orchestrator.config.yaml`. No day-of-week normalization in v0 (revisit after ≥2 weeks of data).
- **Metric polling: every 3h** via driver `GET /metrics`. Heartbeat `GET /health` every 60s; three consecutive failures pause the window clock.
- **Scoring (v0)**: `score = matches_per_hour * 10 + likes_per_hour * 1 + reply_rate_bonus`; keep if `score_delta > 0 AND matches_gained >= 3`. Raw series stored in `metrics.db`; score is a recomputable view.
- **Driver libraries**: `pynput` primary, `cliclick` fallback (M0 decides); `mss` for screencapture; `instructor` + Pydantic for vision-LLM OCR; FastAPI + `httpx`.
- **Container libraries**: APScheduler, `python-telegram-bot`, `httpx`, SQLite via stdlib, `pydantic-settings` for config.
- **Host ops**: launchd for driver with `KeepAlive=true`, `RunAtLoad=true`; `caffeinate -dimsu` wrapper; reconnect logic detects missing iPhone Mirroring window and re-auths.
- **Language & tooling**: strict-typed Python 3.12+ via `pyright`; `uv` for packaging and execution; `ruff` for lint+format.

## Tooling & dev conventions

- **Package management: `uv`.** Each subproject (`container/orchestrator/`, `drivers/macos-iphone-mirroring/`) is its own uv project with `pyproject.toml`, `uv.lock`, and a pinned `.python-version` (`3.12`). Contributors run `uv sync` once and `uv run <tool>` for everything — no global Python or pip activity.
- **Type checking: `pyright` in strict mode.** Config lives in each `pyproject.toml`:
  ```toml
  [tool.pyright]
  typeCheckingMode = "strict"
  pythonVersion = "3.12"
  reportMissingTypeStubs = "warning"
  ```
  Every module annotated. Pydantic at HTTP/DB/IPC boundaries so runtime shapes match static types; `TypedDict`/`dataclass` for internal shapes. No `Any` without a comment justifying it. `uv run pyright .` runs in pre-commit and as a Docker build step for the container side.
- **Lint + format: `ruff`** (`uv run ruff check .` and `uv run ruff format .`).
- **Modern Python idioms**: `from __future__ import annotations` at every module top, PEP 695 type aliases where useful, `match` over `if/elif` chains when dispatching on variant kinds.
- **Dockerfile**: base on `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` with the multi-stage pattern from Astral's docs.
- **Tests**: `pytest` + `pytest-asyncio` + `respx`. Keep the suite small — most real bugs live in record-replay flows, verified by M-series smoke tests.
- **Pre-commit**: one hook chains `uv run ruff check --fix`, `uv run ruff format`, `uv run pyright`.

## Milestones

**M0 — De-risk control surface (Day 1).** Run `drivers/macos-iphone-mirroring/probe.py` against a focused iPhone Mirroring window with Bumble open. Gate: if neither `cliclick` nor `pynput` lands events, pivot driver to wired Android + ADB before any other code is written.

**M1 — macOS driver MVP.** `actions.py` primitives, `record.py` (pynput-based), record 5 flows by hand, `metrics.py` with `instructor` + Pydantic, `verify_region_hash.py`. Acceptance: curl-driven end-to-end edit and metric read works reliably, reconnect works after manually closing iPhone Mirroring.

**M2 — `bumble` CLI + pi skill.** Shell wrapper around `curl ${DRIVER_URL}/flow/...`. pi skill doc. Acceptance: `bumble edit prompt --slot=1 --text="..."` from inside the container changes Bumble.

**M3 — Orchestrator core.** `main.py`, `clock.py`, `metrics_poll.py`, `scoring.py`, `variants.py`, `verify.py`. Config YAML. No pi, no Telegram yet. Acceptance: drives one manual-variant experiment end-to-end with synthetic score handoff on a short window.

**M4 — pi integration + supervisor.** `pi_supervisor.py`, `autoresearch.sh`, `maxIterations=1` per invocation. Acceptance: two back-to-back autonomous experiments with a forced container restart mid-window that recovers cleanly.

**M5 — Approval.** Telegram bot with inline buttons. Acceptance: pi proposes → you Approve on phone → orchestrator applies.

**M6 — Packaging.** Dockerfile, docker-compose.yml, launchd plist, `docs/drivers.md`. Acceptance: clean checkout → `docker compose up` + `launchctl load` → full loop runs.

**M7 — First real run.** Seed 4–6 photos, 3–4 bio drafts. Let it run. Acceptance: pi keeps/discards variants based on real 72h windows for ≥3 experiments without intervention.

## Notes

- **pi-autoresearch's MAD confidence heuristic** was designed for seconds-scale benchmarks. With 72h experiments it will take ≥2 weeks to stabilize. That's fine — it's advisory only; don't over-index on the confidence widget early.
- **Telegram bot token**: `state/secrets.env` (gitignored). Out-of-scope for v0: 2FA, multi-user, admin controls.
- **Cost control**: cap pi's `maxIterations` per-invocation (1–2). Prefer Haiku for proposal generation where possible.
- **iPhone Mirroring session timeout**: Apple disconnects Mirroring on idle and always on host reboot. `reconnect.py` is the primary defense; every flow calls `ensure_connected()` first.
- **Tailscale is optional.** Only needed if you later want to monitor from off-network. Default wiring is localhost.
