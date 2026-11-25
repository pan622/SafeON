from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelSelection(BaseModel):
    model: str


class ApiKeyUpdate(BaseModel):
    model: str
    api_key: str = Field(min_length=8)


class ConnectionTest(BaseModel):
    model: str | None = None
    api_key: str | None = None


class JobResponse(BaseModel):
    job_id: str
    job_type: Literal["extraction", "reasoning"]
    status: str
    progress: int
    stage_message: str
    error: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    download_url: str | None = None
