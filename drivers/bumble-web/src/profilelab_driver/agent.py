"""FastAPI entrypoint for the Bumble Web driver.

Contract in ../../../docs/drivers.md. v0 implements /health and /reconnect
honestly; flow endpoints stay 501 until M1 wires up real Playwright flows.
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

DRIVER_NAME = "bumble-web"


def create_app() -> FastAPI:
    app = FastAPI(
        title="profilelab Bumble Web driver",
        version=__version__,
        description="Playwright-based driver for Bumble Web (bumble.com/app).",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        # v0: the process answering means the driver is up. Once we add a
        # Playwright browser context, this should report whether the browser
        # is alive and whether the logged-in session is valid.
        return HealthResponse(
            ok=True,
            connected=False,
            session_age_s=0,
            driver=DRIVER_NAME,
            version=__version__,
        )

    @app.post("/reconnect", response_model=ReconnectResponse)
    def reconnect() -> ReconnectResponse:
        # v0: no browser context to reconnect yet. M1 will spin up a fresh
        # browser context from the stored state and report back.
        return ReconnectResponse(ok=True, connected=False)

    @app.post(
        "/flow/edit_photo",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_photo(_: EditPhotoRequest) -> FlowResponse:
        raise _not_implemented("edit_photo flow awaits M1 (Playwright)")

    @app.post(
        "/flow/edit_prompt",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_prompt(_: EditPromptRequest) -> FlowResponse:
        raise _not_implemented("edit_prompt flow awaits M1 (Playwright)")

    @app.post(
        "/flow/edit_bio",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def edit_bio(_: EditBioRequest) -> FlowResponse:
        raise _not_implemented("edit_bio flow awaits M1 (Playwright)")

    @app.post(
        "/flow/save_profile",
        response_model=FlowResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def save_profile(_: SaveProfileRequest) -> FlowResponse:
        raise _not_implemented("save_profile flow awaits M1 (Playwright)")

    @app.get(
        "/metrics",
        response_model=MetricsResponse,
        responses={501: {"model": ErrorResponse}},
    )
    def metrics() -> MetricsResponse:
        raise _not_implemented("metrics read awaits M1 (DOM scrape + vision-LLM fallback)")

    return app


def _not_implemented(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=ErrorResponse(error="not_implemented", detail=detail).model_dump(),
    )


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
