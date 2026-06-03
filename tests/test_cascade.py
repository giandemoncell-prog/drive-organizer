from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import make_file
from drive_organizer.ai.cascade import AICascade, _batches, _retry_classify, _fallback
from drive_organizer.ai.base import ClassificationResult
from drive_organizer.strategies.by_type import FileTypeStrategy


def _res(file_id, path, conf=0.9, provider="haiku"):
    return ClassificationResult(
        file_id=file_id, target_path=path, confidence=conf, provider=provider
    )


# ─── _batches ─────────────────────────────────────────────────────────────────

class TestBatches:
    def test_empty(self):
        assert list(_batches([], 5)) == []

    def test_exact_division(self):
        assert list(_batches([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]

    def test_remainder(self):
        assert list(_batches([1, 2, 3], 2)) == [[1, 2], [3]]

    def test_single_item(self):
        assert list(_batches([42], 10)) == [[42]]

    def test_size_one_batches(self):
        assert list(_batches([1, 2, 3], 1)) == [[1], [2], [3]]


# ─── _retry_classify ──────────────────────────────────────────────────────────

class TestRetryClassify:
    def test_success_on_first_attempt(self):
        p = MagicMock()
        p.classify_batch.return_value = ["result"]
        assert _retry_classify(p, [], "hint", None, attempts=0) == ["result"]
        assert p.classify_batch.call_count == 1

    def test_retry_then_success(self):
        p = MagicMock()
        p.classify_batch.side_effect = [RuntimeError("fail"), ["result"]]
        with patch("drive_organizer.ai.cascade.time.sleep"):
            result = _retry_classify(p, [], "hint", None, attempts=1)
        assert result == ["result"]
        assert p.classify_batch.call_count == 2

    def test_all_fail_returns_none(self):
        p = MagicMock()
        p.classify_batch.side_effect = RuntimeError("fail")
        with patch("drive_organizer.ai.cascade.time.sleep"):
            result = _retry_classify(p, [], "hint", None, attempts=2)
        assert result is None
        assert p.classify_batch.call_count == 3  # initial + 2 retries

    def test_zero_attempts_fails_immediately(self):
        p = MagicMock()
        p.classify_batch.side_effect = RuntimeError("fail")
        result = _retry_classify(p, [], "hint", None, attempts=0)
        assert result is None
        assert p.classify_batch.call_count == 1


# ─── _fallback ────────────────────────────────────────────────────────────────

class TestFallback:
    def test_fallback_target_is_altro(self):
        f = make_file(id="xyz")
        res = _fallback(f)
        assert res.file_id == "xyz"
        assert res.target_path == "Altro"
        assert res.confidence == 0.0
        assert res.provider == "deterministic"


# ─── AICascade — deterministic path ──────────────────────────────────────────

class TestAICascadeDeterministic:
    def setup_method(self):
        self.ollama = MagicMock()
        self.ollama.health_check.return_value = False
        self.haiku = MagicMock()
        self.opus = MagicMock()
        self.cascade = AICascade(self.ollama, self.haiku, self.opus)

    def test_file_type_strategy_needs_no_cloud(self):
        files = [
            make_file(id="f1", mime_type="application/pdf"),
            make_file(id="f2", mime_type="image/jpeg"),
        ]
        results = self.cascade.classify_files(files, FileTypeStrategy())
        assert results[0].target_path == "PDF"
        assert results[1].target_path == "Immagini"
        self.haiku.classify_batch.assert_not_called()
        self.opus.classify_batch.assert_not_called()

    def test_cloud_escalations_zero_for_deterministic(self):
        files = [make_file(id="f1", mime_type="application/pdf")]
        self.cascade.classify_files(files, FileTypeStrategy())
        assert self.cascade.cloud_escalations == 0

    def test_result_order_matches_input(self):
        files = [
            make_file(id="a", mime_type="application/pdf"),
            make_file(id="b", mime_type="image/jpeg"),
            make_file(id="c", mime_type="video/mp4"),
        ]
        results = self.cascade.classify_files(files, FileTypeStrategy())
        assert [r.file_id for r in results] == ["a", "b", "c"]


# ─── AICascade — agreement bonus ─────────────────────────────────────────────

class TestAgreementBonus:
    def _make_strategy(self):
        s = MagicMock()
        s.classify_without_ai.return_value = None
        s.allowed_folders.return_value = []
        s.build_prompt_hint.return_value = "hint"
        return s

    def test_bonus_applied_when_ollama_and_haiku_agree(self):
        f = make_file(id="f1", mime_type="application/octet-stream")
        ollama = MagicMock()
        ollama.health_check.return_value = True
        ollama.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="Finanza",
                                 confidence=0.5, provider="ollama")
        ]
        haiku = MagicMock()
        haiku.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="Finanza",
                                 confidence=0.75, provider="haiku")
        ]
        cascade = AICascade(ollama, haiku, MagicMock())
        with patch("drive_organizer.ai.cascade.time.sleep"):
            results = cascade.classify_files([f], self._make_strategy())
        # 0.75 + 0.10 = 0.85
        assert results[0].confidence == pytest.approx(0.85)
        assert "[agreement bonus]" in results[0].reasoning

    def test_no_bonus_when_providers_disagree(self):
        f = make_file(id="f1", mime_type="application/octet-stream")
        ollama = MagicMock()
        ollama.health_check.return_value = True
        ollama.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="Lavoro",
                                 confidence=0.5, provider="ollama")
        ]
        haiku = MagicMock()
        haiku.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="Finanza",
                                 confidence=0.75, provider="haiku")
        ]
        cascade = AICascade(ollama, haiku, MagicMock())
        with patch("drive_organizer.ai.cascade.time.sleep"):
            results = cascade.classify_files([f], self._make_strategy())
        assert results[0].confidence == pytest.approx(0.75)
        assert "agreement bonus" not in results[0].reasoning

    def test_bonus_capped_at_one(self):
        f = make_file(id="f1", mime_type="application/octet-stream")
        ollama = MagicMock()
        ollama.health_check.return_value = True
        ollama.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="X",
                                 confidence=0.5, provider="ollama")
        ]
        haiku = MagicMock()
        haiku.classify_batch.return_value = [
            ClassificationResult(file_id="f1", target_path="X",
                                 confidence=0.95, provider="haiku")
        ]
        cascade = AICascade(ollama, haiku, MagicMock())
        with patch("drive_organizer.ai.cascade.time.sleep"):
            results = cascade.classify_files([f], self._make_strategy())
        assert results[0].confidence <= 1.0


# ─── AICascade — failed batch continues ──────────────────────────────────────

class TestHaikuFailureContinues:
    def _make_strategy(self):
        s = MagicMock()
        s.classify_without_ai.return_value = None
        s.allowed_folders.return_value = []
        s.build_prompt_hint.return_value = "hint"
        return s

    def test_failed_batch_does_not_abort_subsequent_batches(self):
        f1 = make_file(id="f1", mime_type="application/octet-stream")
        f2 = make_file(id="f2", mime_type="application/octet-stream")

        ollama = MagicMock()
        ollama.health_check.return_value = False  # skip ollama entirely

        haiku = MagicMock()
        # f1's batch fails all 3 attempts (initial + 2 retries); f2's batch succeeds
        haiku.classify_batch.side_effect = [
            RuntimeError("rate limit"),
            RuntimeError("rate limit"),
            RuntimeError("rate limit"),
            [ClassificationResult(file_id="f2", target_path="Fogli",
                                  confidence=0.9, provider="haiku")],
        ]

        cascade = AICascade(ollama, haiku, MagicMock())

        with patch("drive_organizer.ai.cascade.time.sleep"), \
             patch("drive_organizer.ai.cascade._BATCH_SIZE", 1):
            results = cascade.classify_files([f1, f2], self._make_strategy())

        targets = {r.file_id: r.target_path for r in results}
        assert targets["f2"] == "Fogli"
        assert targets["f1"] == "Altro"  # no result → fallback
