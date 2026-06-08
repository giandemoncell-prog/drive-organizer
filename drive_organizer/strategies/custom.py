from __future__ import annotations

import re

from pydantic import BaseModel, Field

from drive_organizer.ai.base import ClassificationResult
from drive_organizer.drive.models import DriveFile
from drive_organizer.strategies.base import OrganizationStrategy


class TaxonomyRule(BaseModel):
    match: str
    target: str


class Taxonomy(BaseModel):
    folders: list[str] = Field(default_factory=list)
    rules: list[TaxonomyRule] = Field(default_factory=list)
    fallback_folder: str = "99_Archivio"


def _parse_keywords(match_expr: str) -> list[str]:
    return [k.strip().lower() for k in re.split(r"\bOR\b", match_expr, flags=re.IGNORECASE) if k.strip()]


def _file_searchable(file: DriveFile) -> str:
    parts = [file.name.lower()]
    if file.file_extension:
        parts.append(f".{file.file_extension.lower()}")
    return " ".join(parts)


def _matches_keyword(kw: str, searchable: str) -> bool:
    if kw.startswith("."):
        return kw in searchable
    # Exclude _ from word boundary so underscore-separated names match (e.g. bachata in bachata_vibes)
    pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
    return bool(re.search(pattern, searchable, re.IGNORECASE))


class CustomNLStrategy(OrganizationStrategy):
    name = "custom"
    description = "Struttura personalizzata definita dall'utente via linguaggio naturale"

    def __init__(self, description: str, taxonomy: dict | None = None):
        self._description = description
        self._taxonomy = taxonomy or {}
        self._compiled_rules = self._compile_rules()

    def _compile_rules(self) -> list[tuple[list[str], str]]:
        rules = []
        for rule in self._taxonomy.get("rules", []):
            keywords = _parse_keywords(rule.get("match", ""))
            target = rule.get("target", self._taxonomy.get("fallback_folder", "Altro"))
            if keywords:
                rules.append((keywords, target))
        return rules

    def build_prompt_hint(self) -> str:
        folders = self._taxonomy.get("folders", [])
        rules = self._taxonomy.get("rules", [])
        hint = f"Custom structure: {self._description}\n"
        if folders:
            hint += f"Allowed folders: {', '.join(folders)}\n"
        if rules:
            rules_text = "; ".join(f"{r.get('match','*')} → {r.get('target','Altro')}" for r in rules)
            hint += f"Rules: {rules_text}\n"
        hint += "Use Italian folder names. Set confidence < 0.6 if ambiguous."
        return hint

    def allowed_folders(self) -> list[str]:
        return self._taxonomy.get("folders", ["Altro"])

    def requires_ai(self) -> bool:
        return bool(not self._compiled_rules)

    def classify_without_ai(self, file: DriveFile) -> ClassificationResult | None:
        if not self._compiled_rules:
            return None
        searchable = _file_searchable(file)
        for keywords, target in self._compiled_rules:
            if any(_matches_keyword(kw, searchable) for kw in keywords):
                return ClassificationResult(
                    file_id=file.id,
                    target_path=target,
                    confidence=1.0,
                    reasoning=f"Keyword match → {target}",
                    provider="deterministic",
                )
        fallback = self._taxonomy.get("fallback_folder", "99_Archivio")
        return ClassificationResult(
            file_id=file.id,
            target_path=fallback,
            confidence=0.9,
            reasoning="No rule matched → fallback",
            provider="deterministic",
        )

    def set_taxonomy(self, taxonomy: dict[str, object]) -> None:
        self._taxonomy = taxonomy
        self._compiled_rules = self._compile_rules()
