from __future__ import annotations

from drive_organizer.ai.base import ClassificationResult
from drive_organizer.drive.models import DriveFile
from drive_organizer.strategies.base import OrganizationStrategy

_MONTHS_IT = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
}


class DateStrategy(OrganizationStrategy):
    name = "date"
    description = "Organizza per data di modifica (Anno/Mese)"

    def __init__(self, use_created: bool = False, year_only: bool = False):
        self._use_created = use_created
        self._year_only = year_only

    def build_prompt_hint(self) -> str:
        return "Classify by modification date into Year/Month folders."

    def allowed_folders(self) -> list[str]:
        return []

    def requires_ai(self) -> bool:
        return False

    def classify_without_ai(self, file: DriveFile) -> ClassificationResult:
        dt = file.created_time if self._use_created else file.modified_time
        year = str(dt.year)
        if self._year_only:
            path = year
        else:
            month = _MONTHS_IT[dt.month]
            path = f"{year}/{month}"
        return ClassificationResult(
            file_id=file.id,
            target_path=path,
            confidence=1.0,
            reasoning=f"{'Created' if self._use_created else 'Modified'}: {dt.date()}",
            provider="deterministic",
        )
