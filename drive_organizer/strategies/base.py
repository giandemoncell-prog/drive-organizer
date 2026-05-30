from __future__ import annotations

from abc import ABC, abstractmethod

from drive_organizer.ai.base import ClassificationRequest, ClassificationResult
from drive_organizer.drive.models import DriveFile


class OrganizationStrategy(ABC):
    name: str
    description: str

    @abstractmethod
    def build_prompt_hint(self) -> str:
        """Returns the hint string passed to AI classify_batch."""

    @abstractmethod
    def allowed_folders(self) -> list[str]:
        """Top-level folder names this strategy can create."""

    def classify_without_ai(self, file: DriveFile) -> ClassificationResult | None:
        """Deterministic classification without AI. None = AI required."""
        return None

    def requires_ai(self) -> bool:
        return True
