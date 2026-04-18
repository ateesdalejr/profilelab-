"""Pydantic models for the profilelab driver HTTP contract.

Canonical reference: ../../../docs/drivers.md. These types are the
shared language between orchestrator and driver — keeping them strict
and additive-only preserves cross-driver portability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """Base with strict runtime validation.

    `extra="forbid"` at the request side; responses stay additive-only
    (consumers use `ignore`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Health / session ---------------------------------------------------


class HealthResponse(_Strict):
    ok: bool
    connected: bool
    session_age_s: int = Field(ge=0)
    driver: str
    version: str


class ReconnectResponse(_Strict):
    ok: bool
    connected: bool


# --- Flow requests ------------------------------------------------------


class EditPhotoRequest(_Strict):
    slot: int = Field(ge=1, le=6)
    source_path: str


class EditPromptRequest(_Strict):
    slot: int = Field(ge=1, le=3)
    text: str = Field(min_length=1, max_length=300)


class EditBioRequest(_Strict):
    text: str = Field(max_length=500)


class SaveProfileRequest(_Strict):
    pass


class FlowResponse(_Strict):
    ok: bool
    verified: bool


# --- Metrics ------------------------------------------------------------


class MetricsResponse(_Strict):
    ts: datetime
    likes: int | None = Field(ge=0, default=None)
    matches: int | None = Field(ge=0, default=None)
    confidence: float = Field(ge=0.0, le=1.0)


# --- Errors -------------------------------------------------------------

ErrorCode = Literal[
    "apply_failed",
    "not_connected",
    "session_expired",
    "verification_failed",
    "not_implemented",
    "platform_error",
    "invalid_request",
]


class ErrorResponse(_Strict):
    error: ErrorCode
    detail: str
