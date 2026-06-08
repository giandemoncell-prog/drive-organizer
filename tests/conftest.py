import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SignatureCache to a per-test temp file.

    Prevents cross-test and cross-run contamination: cascade tests that write
    a cache entry no longer affect subsequent cache unit tests, and vice versa.
    """
    monkeypatch.setattr(
        "drive_organizer.ai.cache._DEFAULT_CACHE_PATH",
        tmp_path / "test_cache.json",
    )
