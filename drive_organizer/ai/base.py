from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict, Field


class ClassificationRequest(BaseModel):
    """Privacy boundary: only metadata, never file content. Frozen to prevent mutation."""
    model_config = ConfigDict(frozen=True)

    file_id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: datetime
    extension: str | None = None


class ClassificationResult(BaseModel):
    file_id: str
    target_path: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    provider: Literal["ollama", "haiku", "opus", "deterministic"]
    used_content: bool = False


@runtime_checkable
class AIProvider(Protocol):
    def classify_batch(
        self,
        requests: list[ClassificationRequest],
        strategy_hint: str,
        allowed_folders: list[str] | None = None,
    ) -> list[ClassificationResult]: ...

    def health_check(self) -> bool: ...
