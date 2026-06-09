#!/usr/bin/env python3
"""Interactive .env configurator for Drive Organizer."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

ENV_FIELDS = [
    ("ANTHROPIC_API_KEY",          "Anthropic API key (sk-ant-...)"),
    ("GEMINI_API_KEY",             "Gemini API key (AIza...)"),
    ("OLLAMA_MODEL",               "Modello Ollama"),
    ("OLLAMA_BASE_URL",            "URL Ollama"),
    ("OLLAMA_CONFIDENCE_THRESHOLD","Soglia confidenza Ollama (0.0-1.0)"),
    ("HAIKU_CONFIDENCE_THRESHOLD", "Soglia confidenza Haiku (0.0-1.0)"),
    ("MAX_CLOUD_ESCALATIONS",      "Max escalazioni cloud (cost control)"),
]


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                data[k.strip()] = v.strip()
    return data


def save_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    written: set[str] = set()
    result = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            result.append(line)
            continue
        k = s.split("=", 1)[0].strip()
        if k in updates:
            result.append(f"{k}={updates[k]}")
            written.add(k)
        else:
            result.append(line)
    for k, v in updates.items():
        if k not in written:
            result.append(f"{k}={v}")
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


def mask(val: str) -> str:
    placeholders = {"sk-ant-...", "AIza...", ""}
    if not val or val in placeholders:
        return "(non impostata)"
    if len(val) > 10:
        return val[:6] + "..." + val[-2:]
    return val


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"\n[ERRORE] {env_path} non trovato.")
        print("Esegui prima install.bat\n")
        sys.exit(1)

    current = load_env(env_path)

    print()
    print("=" * 48)
    print("  Drive Organizer — Configurazione")
    print("  Premi INVIO per mantenere il valore attuale.")
    print("=" * 48)
    print()

    updates: dict[str, str] = {}

    for key, label in ENV_FIELDS:
        curr = current.get(key, "")
        try:
            val = input(f"  {label}\n  [{mask(curr)}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Annullato.\n")
            sys.exit(0)
        if val:
            updates[key] = val
        print()

    if updates:
        save_env(env_path, updates)
        n = len(updates)
        print(f"  {n} impostazion{'e' if n == 1 else 'i'} salvat{'a' if n == 1 else 'e'} in .env\n")
    else:
        print("  Nessuna modifica.\n")


if __name__ == "__main__":
    main()
