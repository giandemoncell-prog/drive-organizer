from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from drive_organizer.drive.models import MoveOperation, OrganizationPlan
from drive_organizer.executor import PlanExecutor
from tests.helpers import make_file


def _make_plan(moves: list[MoveOperation], folders: list[str] | None = None) -> OrganizationPlan:
    return OrganizationPlan(
        strategy_name="type",
        moves=moves,
        folders_to_create=folders or [],
        total_files=len(moves),
    )


def _make_move(file_id: str = "f1", file_name: str = "doc.pdf", target: str = "01_Docs") -> MoveOperation:
    return MoveOperation(
        file_id=file_id,
        file_name=file_name,
        source_parents=["root"],
        target_path=target,
        confidence=0.9,
        provider="ollama",
    )


@pytest.fixture()
def client(tmp_path):
    c = MagicMock()
    c.get_or_create_folder_path.return_value = "folder_id_123"
    c.batch_move.return_value = []  # no failures
    return c


@pytest.fixture()
def executor(client, tmp_path, monkeypatch):
    monkeypatch.setattr("drive_organizer.executor.settings.rollback_dir", str(tmp_path))
    return PlanExecutor(client, user_email="test@example.com")


class TestExecuteEmptyPlan:
    def test_returns_manifest_with_no_entries(self, executor):
        plan = _make_plan([])
        manifest = executor.execute(plan)
        assert manifest.entries == []
        assert manifest.drive_user_email == "test@example.com"
        assert manifest.strategy == "type"

    def test_lock_released_after_empty_run(self, executor, tmp_path):
        executor.execute(_make_plan([]))
        assert not (tmp_path / ".lock").exists()


class TestExecuteMoves:
    def test_calls_batch_move(self, executor, client):
        plan = _make_plan([_make_move()], folders=["01_Docs"])
        executor.execute(plan)
        client.batch_move.assert_called_once()

    def test_creates_folders(self, executor, client):
        plan = _make_plan([_make_move()], folders=["01_Docs", "02_Images"])
        executor.execute(plan)
        assert client.get_or_create_folder_path.call_count == 2

    def test_manifest_saved_to_disk(self, executor, tmp_path):
        plan = _make_plan([_make_move()])
        executor.execute(plan)
        saved = list(tmp_path.glob("rollback_*.json"))
        assert len(saved) == 1

    def test_skipped_moves_not_executed(self, executor, client):
        skipped = MoveOperation(
            file_id="skip1", file_name="skip.pdf",
            source_parents=["root"], target_path="01_Docs",
            confidence=0.9, provider="ollama", skipped=True,
        )
        plan = _make_plan([skipped])
        executor.execute(plan)
        client.batch_move.assert_called_once()
        # batch_move is called with empty active list
        active_passed = client.batch_move.call_args[0][0]
        assert active_passed == []

    def test_lock_released_after_successful_run(self, executor, tmp_path):
        executor.execute(_make_plan([_make_move()]))
        assert not (tmp_path / ".lock").exists()


class TestExecutePartialFailure:
    def test_manifest_completed_despite_failures(self, executor, client):
        client.batch_move.return_value = ["f1"]  # f1 failed
        plan = _make_plan([_make_move(file_id="f1"), _make_move(file_id="f2")])
        manifest = executor.execute(plan)
        # manifest still returns
        assert manifest.completed_at is not None

    def test_lock_released_on_exception(self, executor, client, tmp_path):
        client.get_or_create_folder_path.side_effect = RuntimeError("Drive error")
        plan = _make_plan([_make_move()], folders=["01_Docs"])
        with pytest.raises(RuntimeError, match="Drive error"):
            executor.execute(plan)
        assert not (tmp_path / ".lock").exists()


class TestLock:
    def test_concurrent_run_raises(self, executor, tmp_path):
        (tmp_path / ".lock").write_text("99999")
        with pytest.raises(RuntimeError, match="Another run is active"):
            executor.execute(_make_plan([]))
