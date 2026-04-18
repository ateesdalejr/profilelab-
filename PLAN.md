# profilelab v0 — Execution Plan

## Context

profilelab is an autonomous experiment-loop app that iteratively edits a Bumble profile and optimizes it against **real match/engagement metrics** (not an LLM-as-judge proxy). The optimization loop is [`pi-autoresearch`](https://github.com/davebcn87/pi-autoresearch) — an extension for the `pi` CLI agent that treats optimization as `edit → benchmark → keep-or-revert → repeat`.

Hard constraints:
1. **Days-per-experiment cadence**: each variant needs a 72h real-world window to observe matches/likes. pi must be parked between experiments and resumed via its built-in session-resume mechanism (`autoresearch.md` + `autoresearch.jsonl`).
2. **Cross-platform reproducibility**: the system must build and run anywhere Docker runs.
3. **Profile edits only**: no automated swipes (Bumble ToS).

The original plan targeted the iPhone Bumble app via macOS iPhone Mirroring. **M0 (2026-04-17) confirmed Apple filters synthetic events into iPhone Mirroring** — neither `cliclick` nor `pynput` could land clicks. The project pivoted to **Bumble Web (`https://bumble.com/app`) driven by Playwright in-container**. A follow-up probe confirmed Playwright loads Bumble Web cleanly, no bot-wall challenge, login UI reachable.

This pivot made the system simpler: no host agent, no macOS-specific code, nothing outside the container.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Container (portable, Docker)                              │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ pi + pi-autoresearch                                 │ │
│ │   autoresearch.sh reads pending/exp-N.score, exits   │ │
│ │   writes variant spec + proposal marker to state/    │ │
│ │   calls `bumble` CLI via shell                       │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ orchestrator (Python daemon)                         │ │
│ │  APScheduler: 72h windows, 3h metric polls           │ │
│ │  metrics poller → state/metrics.db                   │ │
│ │  scoring.py → pending/exp-N.score                    │ │
│ │  variant queue + Telegram approval gate              │ │
│ │  pi supervisor (kill / relaunch per experiment)      │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ driver (FastAPI + Playwright, listens on :8765)      │ │
│ │  POST /flow/edit_photo|edit_prompt|edit_bio|save_*   │ │
│ │  GET  /metrics — DOM scrape, vision-LLM fallback     │ │
│ │  GET  /health — reports browser context liveness     │ │
│ │  Persistent Playwright user-data-dir for session     │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                            │
└──────────────────────────────────────────────────────────┘
                              │
                              │ bind-mounted volumes
                              ▼
              state/            (specs, SQLite, pending/, variants/)
              browser-state/    (Playwright user-data-dir; gitignored)
```

### Driver contract

The HTTP contract is the pluggability surface. Stable endpoints (full spec in `docs/drivers.md`):

```
POST /flow/edit_photo          { slot, source_path }    → { ok, verified }
POST /flow/edit_prompt         { slot, text }           → { ok, verified }
POST /flow/edit_bio            { text }                 → { ok, verified }
POST /flow/save_profile        {}                       → { ok, verified }
GET  /metrics                                            → { ts, likes, matches, confidence }
GET  /health                                             → { ok, connected, session_age_s }
POST /reconnect                                          → { ok, connected }
```

A future LinkedIn / Hinge / Android-ADB / etc. driver is a sibling sub-project implementing the same endpoints. The container's `bumble` CLI only cares about the HTTP shape.

### Per-experiment flow (pi is disposable)

1. pi writes `state/variants/exp-N.yaml` (the spec) + a proposal marker.
2. Orchestrator sees proposal → sends Telegram approve/reject → on approve, calls driver flows to apply. On failure or reject, writes `score=null, status=skipped`, moves on.
3. `verify_applied`: driver re-reads the profile via DOM scrape, confirms edits match the spec. Mismatch → retry once, else mark failed.
4. Window starts. `variant_live_at` recorded. Orchestrator kills pi.
5. Every 3h, orchestrator polls driver `GET /metrics` → appends to `state/metrics.db`. Heartbeat on `/health`; consecutive failures pause the clock (dead time doesn't count as signal).
6. At `variant_live_at + 72h`, orchestrator computes score → writes `state/pending/exp-N.score`.
7. Orchestrator relaunches pi via `pi /autoresearch "exp-N score ready, continue"`. pi reads `autoresearch.md` + jsonl, re-runs `autoresearch.sh` which now reads the score file and emits `METRIC engagement=<n>`. pi runs its keep/revert logic.
8. On revert, orchestrator re-applies the baseline spec from `state/live_profile.json`. `verify_applied` before continuing.
9. pi proposes next variant; loop.

### State layout (`state/` — bind-mounted, partly git-tracked)

```
state/
├── autoresearch.md           # pi-autoresearch session doc (committed)
├── autoresearch.jsonl        # pi-autoresearch run log (gitignored, large/churn)
├── autoresearch.sh           # benchmark: reads pending/exp-N.score, emits METRIC
├── live_profile.json         # ground truth of what's currently on Bumble
├── variants/
│   ├── baseline.yaml         # initial profile spec
│   └── exp-N.yaml            # immutable per-experiment specs
├── proposals/                # pi-proposed variants awaiting approval
├── pending/                  # orchestrator → pi handoff (gitignored)
├── metrics.db                # SQLite (gitignored)
└── photos/                   # source photo pool (gitignored — personal)
```

Separately, `browser-state/` holds the persistent Playwright `user-data-dir` (cookies + storage after login). Bind-mounted, gitignored.

## Key decisions

- **Everything in-container.** No host agent. pi, orchestrator, and Playwright driver all run inside one Docker image (with the driver as a separate FastAPI process so process isolation is preserved and the HTTP contract stays honest).
- **Bumble Web as the control surface.** `https://bumble.com/app`. Confirmed loadable by Playwright headless in the M0b probe.
- **Playwright with a persistent `user-data-dir`** at `browser-state/`. User logs in manually once; driver reuses saved session. SMS auth is never automated.
- **pi is disposable between experiments.** Orchestrator kills and resumes pi via `/autoresearch <text>` once the score file lands.
- **State is spec-based, not git-branch-based.** `state/live_profile.json` is source of truth; variants are immutable YAML specs; git commits the state dir for audit only.
- **`verify_applied` gates the window.** DOM re-scrape to confirm spec matches. Failed applies are marked, not measured.
- **`bumble` CLI, not MCP.** pi learns it via a pi skill. Driver URL via `DRIVER_URL` env var (default `http://localhost:8765`).
- **Approval via Telegram.** `python-telegram-bot` with inline Approve/Reject buttons. pi never blocks on approval.
- **Window length: 72h, configurable.** No day-of-week normalization in v0.
- **Metric polling: every 3h.** DOM scrape primary; vision-LLM (`instructor`) fallback if Bumble hides counts behind rendered images.
- **Scoring (v0)**: `score = matches_per_hour * 10 + likes_per_hour * 1 + reply_rate_bonus`; keep if `score_delta > 0 AND matches_gained >= 3`. Raw series in `metrics.db`; score is a recomputable view.
- **Driver libraries**: Playwright, FastAPI/uvicorn, Pydantic, `instructor` + `anthropic` (fallback OCR).
- **Container libraries**: APScheduler, `python-telegram-bot`, `httpx`, SQLite via stdlib, `pydantic-settings`.
- **Language & tooling**: strict-typed Python 3.12+ via `pyright`; `uv` for packaging and execution; `ruff` for lint+format.

## Tooling & dev conventions

- **Package management: `uv`.** Each subproject (`container/orchestrator/`, `drivers/bumble-web/`) has its own `pyproject.toml`, `uv.lock`, `.python-version` (`3.12`). Contributors run `uv sync` and `uv run <tool>` for everything — no global Python or pip.
- **Type checking: `pyright` strict.** Every module annotated. Pydantic at HTTP/IPC boundaries so runtime shapes match static types. No `Any` without justification. `uv run pyright` runs in pre-commit and as a Docker build step.
- **Lint + format: `ruff`** (`uv run ruff check` and `uv run ruff format`).
- **Modern Python**: `from __future__ import annotations`, PEP 695 aliases, `match` for variant dispatch.
- **Dockerfile**: base on `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, multi-stage (builder `uv sync --frozen --no-dev`, final copies `.venv`). `playwright install --with-deps chromium` in the builder.
- **Tests**: `pytest` + `pytest-asyncio` + `respx` (mock the driver HTTP boundary from the orchestrator side).
- **Pre-commit**: one hook chains `uv run ruff check --fix`, `uv run ruff format`, `uv run pyright`.

## Milestones

**M0 — Control-surface de-risk (DONE, 2026-04-17).**
- **M0a (iPhone Mirroring, NO-GO)**: `cliclick` and `pynput` both failed to deliver events into iPhone Mirroring. Apple filters synthetic events into the mirrored surface.
- **M0b (Bumble Web + Playwright, GO)**: Playwright headless loads `https://bumble.com/app`, login UI reachable, no bot-wall challenge. Driver strategy pivoted to Bumble Web.

**M1 — Driver flows over Playwright (weekend).**
- Build a `PlaywrightDriver` class encapsulating a long-lived browser context backed by `browser-state/`.
- Replace 501 stubs in `agent.py` with real flow implementations: `edit_photo` (hidden `<input type="file">`), `edit_prompt` (dropdown + textarea), `edit_bio` (textarea), `save_profile`, `read_metrics` (DOM scrape).
- Add `verify_applied` helper that re-scrapes profile state and diffs against the submitted spec.
- Write a manual-login helper: `uv run python -m profilelab_driver.login` opens a headed browser, user completes SMS auth, Playwright saves state.
- **Acceptance**: `curl` round-trip from terminal does a real photo + prompt + bio edit and reads metrics, with `verified: true` reliably.

**M2 — `bumble` CLI + pi skill (half-day).**
- Shell wrapper around `curl ${DRIVER_URL}/flow/...`.
- pi skill in `container/pi-skill/profilelab/SKILL.md`.
- **Acceptance**: `bumble edit prompt --slot=1 --text="..."` from any shell changes Bumble Web.

**M3 — Orchestrator core (weekend).**
- `main.py`, `clock.py`, `metrics_poll.py`, `scoring.py`, `variants.py`, `verify.py`. Config via `orchestrator.config.yaml`.
- No pi, no Telegram yet — drive one manual-variant experiment end-to-end with synthetic score handoff.
- **Acceptance**: orchestrator reads a seeded variant, calls `bumble apply`, verifies, polls metrics for a short window (e.g. 10 min smoke), writes a score file.

**M4 — pi integration + supervisor (weekend).**
- `pi_supervisor.py`, `autoresearch.sh`, `maxIterations=1` per invocation.
- **Acceptance**: two back-to-back autonomous experiments including a forced container restart mid-window that recovers cleanly.

**M5 — Telegram approval (half-day).**
- Bot with `/pending`, `/status`, inline Approve/Reject.
- **Acceptance**: pi proposes → phone notification → one-tap approve → orchestrator applies.

**M6 — Packaging (day).**
- Dockerfile (multi-stage uv + playwright install), docker-compose.yml, updated `docs/drivers.md` with web-driver authoring notes.
- **Acceptance**: clean checkout → `docker compose up` → full loop runs; works on Linux host too (verify via Docker Linux container).

**M7 — First real run (weeks).**
- Seed 4–6 photos, 3–4 bio drafts, 2 prompt variants.
- Let it run. Tune window length and scoring formula based on observed variance.
- **Acceptance**: pi keeps/discards variants based on real 72h windows for ≥3 experiments without intervention.

## Notes

- **pi-autoresearch's MAD confidence heuristic** was designed for seconds-scale benchmarks. With 72h experiments it will take ≥2 weeks to stabilize. Advisory only; don't over-index early.
- **Telegram bot token**: `state/secrets.env`, gitignored. v0 is single-user.
- **Cost control**: cap pi's `maxIterations` per-invocation (1–2). Prefer Haiku for proposal generation where possible.
- **Bumble bot detection**: confirmed not blocking the initial page load. If it escalates later, mitigations in priority order: `--headed` with Xvfb, persistent real-user data dir, `playwright-stealth`, residential proxy.
- **Photo uploads**: target the hidden `<input type="file">` directly (Playwright `set_input_files`); visible upload buttons often have their click events intercepted.
- **Session durability**: Bumble Web sessions can be weeks but may expire. Driver's `/health` reports `connected=false` when the session is dead; orchestrator pauses the clock and pings you via Telegram to re-login.
