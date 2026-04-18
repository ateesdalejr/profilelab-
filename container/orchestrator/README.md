# profilelab — orchestrator

Long-running daemon that owns the experiment clock, polls the driver for metrics, computes scores, gates variant application on human approval (Telegram), and supervises the `pi` process lifecycle across the 72h per-experiment windows.

Runs inside the profilelab Docker container alongside `pi` + `pi-autoresearch`. Talks to the platform driver over HTTP (default `http://host.docker.internal:8765`).

## Setup

```sh
uv sync
uv run pyright
uv run ruff check .
```

Config lives in `orchestrator.config.yaml` at the container's working directory; secrets (Telegram bot token, LLM keys) in `state/secrets.env`.

See `../../PLAN.md` for architecture and `../../docs/drivers.md` for the driver contract this orchestrator depends on.
