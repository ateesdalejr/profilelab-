# profilelab

An autonomous experiment loop that iteratively edits your dating/social profile and optimizes it against **real engagement metrics** — not an LLM judge. Uses [`pi-autoresearch`](https://github.com/davebcn87/pi-autoresearch) as the `try → measure → keep-or-revert → repeat` engine.

v0 is Bumble-only via a macOS iPhone Mirroring driver. The architecture is platform-agnostic (see `docs/drivers.md`); Linux/Android/other platform drivers can plug in later.

## Docs

- **[PLAN.md](./PLAN.md)** — architecture, per-experiment flow, milestones, scoring.
- **[docs/drivers.md](./docs/drivers.md)** — HTTP contract new drivers must satisfy.
- **[drivers/macos-iphone-mirroring/README.md](./drivers/macos-iphone-mirroring/README.md)** — v0 driver + M0 probe instructions.
- **[container/orchestrator/README.md](./container/orchestrator/README.md)** — orchestrator daemon.

## Current state

Scaffolding only. **M0 is the next step**: run the driver probe against iPhone Mirroring with Bumble open to verify synthetic events actually land. If they don't, the whole plan needs a different driver strategy before further code. See the driver README for the probe command.
