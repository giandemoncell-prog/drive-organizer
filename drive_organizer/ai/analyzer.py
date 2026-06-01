from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

from drive_organizer.drive.models import DriveFile

_SAMPLE_SIZE = 400
_MAX_FOLDERS_SHOWN = 30

_SYSTEM_PROMPT = """Sei un esperto di organizzazione file e Google Drive.
Il tuo compito è analizzare l'inventario reale di un Google Drive e proporre
una struttura di cartelle PERSONALIZZATA basata esattamente sui file presenti.

REGOLE FONDAMENTALI:
- Usa nomi di cartella in italiano, chiari e pratici
- Numera le cartelle principali (01_, 02_, ...) per ordinarle
- Proponi da 8 a 16 cartelle top-level (non di più)
- Le regole devono usare parole chiave REALI trovate nei nomi dei file
- Non inventare categorie che non esistono nei dati
- Adatta la struttura al contesto reale (professionale, personale, scolastico...)
- Includi sempre una cartella 99_Archivio per file vecchi/non classificabili

Rispondi SOLO con JSON valido nel formato specificato. Nessun testo prima o dopo."""

_USER_TEMPLATE = """Ecco l'inventario reale del Google Drive da organizzare.

## Statistiche
- Totale file: {total_files}
- Totale cartelle esistenti: {total_folders}

## Distribuzione per tipo (top 20)
{ext_distribution}

## Campione nomi file ({sample_count} file rappresentativi)
{file_samples}

## Cartelle esistenti principali (struttura attuale)
{existing_folders}

---
Analizza questi dati e proponi una struttura di cartelle PERSONALIZZATA.
Restituisci JSON con questo schema esatto:
{{
  "_description": "Breve descrizione della struttura proposta",
  "_reasoning": "Perché hai scelto questa struttura (2-3 righe)",
  "folders": ["01_NomeCartella", "02_NomeCartella", ...],
  "rules": [
    {{
      "match": "parola1 OR parola2 OR parola3",
      "target": "01_NomeCartella",
      "description": "Cosa va in questa cartella"
    }}
  ],
  "fallback_folder": "99_Archivio"
}}"""


def _build_profile(
    files: list[DriveFile],
    existing_top_folders: list[str],
) -> dict:
    """Build statistical profile from actual Drive files."""
    ext_counter: Counter = Counter()
    name_samples_by_ext: dict[str, list[str]] = {}

    for f in files:
        ext = (f.file_extension or Path(f.name).suffix.lstrip(".") or "?").lower()
        ext_counter[ext] += 1
        if ext not in name_samples_by_ext:
            name_samples_by_ext[ext] = []
        if len(name_samples_by_ext[ext]) < 20:
            name_samples_by_ext[ext].append(f.name)

    # Build representative sample: prioritize diversity over quantity
    samples: list[str] = []
    top_exts = [ext for ext, _ in ext_counter.most_common(30)]
    for ext in top_exts:
        names = name_samples_by_ext.get(ext, [])
        take = max(1, min(15, _SAMPLE_SIZE // max(len(top_exts), 1)))
        samples.extend(names[:take])

    # Fill remaining with random
    all_names = [f.name for f in files if f.name]
    remaining = _SAMPLE_SIZE - len(samples)
    if remaining > 0 and all_names:
        extras = random.sample(all_names, min(remaining, len(all_names)))
        samples.extend(extras)

    samples = list(dict.fromkeys(samples))[:_SAMPLE_SIZE]  # deduplicate, cap

    return {
        "total_files": len(files),
        "ext_counter": ext_counter,
        "samples": samples,
        "existing_top_folders": existing_top_folders[:_MAX_FOLDERS_SHOWN],
    }


def _format_prompt(profile: dict, existing_folders: list[str]) -> str:
    ext_lines = "\n".join(
        f"  .{ext}: {count} file"
        for ext, count in profile["ext_counter"].most_common(20)
    )
    sample_lines = "\n".join(f"  - {name}" for name in profile["samples"])
    folders_text = "\n".join(f"  - {f}" for f in existing_folders[:_MAX_FOLDERS_SHOWN])

    return _USER_TEMPLATE.format(
        total_files=profile["total_files"],
        total_folders=len(existing_folders),
        ext_distribution=ext_lines,
        sample_count=len(profile["samples"]),
        file_samples=sample_lines,
        existing_folders=folders_text,
    )


def _call_gemini(prompt: str) -> dict:
    from google import genai
    from google.genai import types
    from drive_organizer.config import settings

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_pro_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    raw = resp.text
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    return json.loads(raw)


def _call_deepseek(prompt: str) -> dict:
    import httpx
    from drive_organizer.config import settings

    resp = httpx.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": settings.deepseek_flash_model,  # V3 chat, not R1 reasoner
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    return json.loads(raw)


def _call_qwen(prompt: str) -> dict:
    import httpx
    from drive_organizer.config import settings

    resp = httpx.post(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.dashscope_api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": settings.qwen_pro_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    return json.loads(raw)


def analyze_and_propose(
    files: list[DriveFile],
    existing_top_folders: list[str],
) -> dict:
    """
    Analyze actual Drive files and propose a personalized taxonomy.
    Tries providers in order: Gemini → DeepSeek → Qwen.
    Only file metadata (names, extensions) is sent — never content.
    """
    from drive_organizer.config import settings

    profile = _build_profile(files, existing_top_folders)
    prompt = _format_prompt(profile, existing_top_folders)

    last_error = None
    if settings.gemini_api_key:
        try:
            return _call_gemini(prompt)
        except Exception as e:
            last_error = e

    if settings.deepseek_api_key:
        try:
            return _call_deepseek(prompt)
        except Exception as e:
            last_error = e

    if settings.dashscope_api_key:
        try:
            return _call_qwen(prompt)
        except Exception as e:
            last_error = e

    raise RuntimeError(
        f"Nessun provider AI disponibile. Configura almeno una API key. "
        f"Ultimo errore: {last_error}"
    )
