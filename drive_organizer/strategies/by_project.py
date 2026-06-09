from __future__ import annotations

from drive_organizer.strategies.base import OrganizationStrategy

_DEFAULT_FOLDERS = [
    "Lavoro", "Personale", "Finanza", "Viaggi", "Foto", "Video",
    "Sviluppo", "Clienti", "Fatture", "Contratti", "Formazione", "Altro",
]


class ProjectTopicStrategy(OrganizationStrategy):
    name = "project"
    description = "Raggruppa per progetto/argomento (analisi semantica del nome)"

    def __init__(self, custom_folders: list[str] | None = None):
        self._folders = custom_folders or _DEFAULT_FOLDERS

    def build_prompt_hint(self) -> str:
        return (
            "Group files by project or topic based on their names. "
            f"Preferred groups: {', '.join(self._folders)}. "
            "Create sub-folders if needed (e.g. Clienti/Acme). "
            "Use Italian folder names. Set confidence < 0.6 if the name is ambiguous."
        )

    def allowed_folders(self) -> list[str]:
        return self._folders

    def requires_ai(self) -> bool:
        return True
