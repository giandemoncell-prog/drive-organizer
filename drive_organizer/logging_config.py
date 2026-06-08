from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_file: str = "logs/drive_organizer.log", level: int = logging.INFO) -> None:
    """Configure file-based rotating log for drive_organizer.* loggers."""
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)

    root = logging.getLogger("drive_organizer")
    if root.handlers:
        return

    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
