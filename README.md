# profilelab

An autonomous experiment loop that iteratively edits your dating/social profile and optimizes it against **real engagement metrics** — not an LLM judge. Uses [`pi-autoresearch`](https://github.com/davebcn87/pi-autoresearch) as the `try → measure → keep-or-revert → repeat` engine.

v0 targets **Bumble via Bumble Web (`bumble.com/app`) driven by Playwright**. The whole system runs in-container and is cross-platform (anywhere Docker runs). The driver abstraction is HTTP-based so other platforms (LinkedIn, Hinge, Android/ADB, etc.) can plug in later as sibling driver sub-projects.

## Docs

- **[PLAN.md](./PLAN.md)** — architecture, per-experiment flow, milestones, scoring.
- **[docs/drivers.md](./docs/drivers.md)** — HTTP contract any new driver must satisfy.
- **[drivers/bumble-web/README.md](./drivers/bumble-web/README.md)** — v0 driver + M0 probe instructions.
- **[container/orchestrator/README.md](./container/orchestrator/README.md)** — orchestrator daemon.

## Current state

- **M0 complete.** Initial plan (iPhone Mirroring + `cliclick`/`pynput`) failed — Apple filters synthetic events into the mirrored surface. Pivot: Bumble Web + Playwright in-container. The Playwright probe loads Bumble Web cleanly, no bot-wall, login UI reachable.
- **M1 next**: real Playwright-driven profile edit flows (photo, prompt, bio, save, metrics) and a manual-login helper for the persistent `user-data-dir`. See `PLAN.md`.
