"""FastAPI entrypoint for the macOS iPhone Mirroring driver.

Contract in ../../../docs/drivers.md. v0 implements /health and /reconnect;
flow endpoints return 501 until M0 clears and record-replay is wired up.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from . import __version__
from .schemas import (
    EditBioRequest,
    EditPhotoRequest,
    EditPromptRequest,
    ErrorResponse,
    FlowResponse,
    HealthResponse,
    MetricsResponse,
    ReconnectResponse,
    SaveProfileRequest,
)
from .session import SessionTracker

DRIVER_NAME = "macos-iphone-mirroring"


def create_app() -> FastAPI:
    app = FastAPI(
        title="profilelab macOS driver",
        version=__version__,
        description="iPhone Mirroring + cliclick/pynput driver for profilelab.",
    )
    tracker = SessionTracker()
    app.state.session_tracker = tracker

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        state = tracker.refresh()
        return HealthResponse(
            ok=True,
            connected=state.connected,
            session_age_s=state.session_age_s,
            driver=DRIVER_NAME,
            version=__version__,
        )

    @app.post("/reconnect", response_model=ReconnectResponse)
    def reconnect() -> ReconnectResponse:
        # v0: iPhone Mirroring reconnect requires a real user action (Touch ID /
        # click the menu bar). We refresh state and report honestly. M1's
        # reconnect.py will add best-effort relaunch via `open -a`.
        state = tracker.refresh()
        return ReconnectResponse(ok=True, connected=state.connected)

    @app.post(
        "/flow/edit_photo",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_photo(_: EditPhotoRequest) -> FlowResponse:
        raise _not_implemented("edit_photo flow awaits M1 (record-replay)")

    @app.post(
        "/flow/edit_prompt",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_prompt(_: EditPromptRequest) -> FlowResponse:
        raise _not_implemented("edit_prompt flow awaits M1 (record-replay)")

    @app.post(
        "/flow/edit_bio",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_bio(_: EditBioRequest) -> FlowResponse:
        raise _not_implemented("edit_bio flow awaits M1 (record-replay)")

    @app.post(
        "/flow/save_profile",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def save_profile(_: SaveProfileRequest) -> FlowResponse:
        raise _not_implemented("save_profile flow awaits M1 (record-replay)")

    @app.get(
        "/metrics",
        response_model=MetricsResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def metrics() -> MetricsResponse:
        raise _not_implemented("metrics read awaits M1 (vision-LLM OCR)")

    return app


def _not_implemented(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=ErrorResponse(error="not_implemented", detail=detail).model_dump(),
    )


# uvicorn entrypoint: `uv run uvicorn profilelab_driver.agent:app`
app = create_app()


def main() -> None:
    """Console script — `uv run profilelab-driver`."""
    import uvicorn

    uvicorn.run(
        "profilelab_driver.agent:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
