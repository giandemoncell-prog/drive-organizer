from tests.helpers import make_file
from drive_organizer.ai.cache import SignatureCache
from drive_organizer.ai.base import ClassificationResult


def _res(path="PDF") -> ClassificationResult:
    return ClassificationResult(
        file_id="x", target_path=path, confidence=0.9, provider="deterministic"
    )


class TestSignatureCache:
    def setup_method(self):
        self.cache = SignatureCache()

    def test_miss_on_empty(self):
        assert self.cache.get(make_file()) is None

    def test_set_then_get(self):
        f = make_file(mime_type="application/pdf", file_extension="pdf", size=5000)
        res = _res("PDF")
        self.cache.set(f, res)
        assert self.cache.get(f) is res

    def test_first_write_wins(self):
        f = make_file(mime_type="application/pdf", file_extension="pdf", size=5000)
        first, second = _res("PDF"), _res("Altro")
        self.cache.set(f, first)
        self.cache.set(f, second)
        assert self.cache.get(f) is first

    def test_different_extension_no_collision(self):
        f_pdf = make_file(mime_type="application/pdf", file_extension="pdf", size=5000)
        f_doc = make_file(mime_type="application/msword", file_extension="doc", size=5000)
        self.cache.set(f_pdf, _res("PDF"))
        assert self.cache.get(f_doc) is None

    def test_same_signature_shared_across_filenames(self):
        # Two files with same extension + size bucket + mime share one cache slot
        f1 = make_file(id="a", name="one.pdf", mime_type="application/pdf",
                       file_extension="pdf", size=5000)
        f2 = make_file(id="b", name="two.pdf", mime_type="application/pdf",
                       file_extension="pdf", size=7000)  # same bucket: small
        res = _res("PDF")
        self.cache.set(f1, res)
        assert self.cache.get(f2) is res

    def test_size_bucket_boundary_different_buckets(self):
        f_tiny = make_file(mime_type="application/pdf", file_extension="pdf", size=999)
        f_small = make_file(mime_type="application/pdf", file_extension="pdf", size=10_001)
        self.cache.set(f_tiny, _res("Tiny"))
        assert self.cache.get(f_small) is None

    def test_none_size_maps_to_native(self):
        f = make_file(mime_type="application/vnd.google-apps.document", size=None)
        res = _res("Documenti")
        self.cache.set(f, res)
        f2 = make_file(mime_type="application/vnd.google-apps.document", size=None)
        assert self.cache.get(f2) is res

    def test_size_counter(self):
        assert self.cache.size() == 0
        self.cache.set(make_file(mime_type="application/pdf", file_extension="pdf"), _res())
        assert self.cache.size() == 1
        self.cache.set(make_file(mime_type="image/jpeg", file_extension="jpg"), _res("Immagini"))
        assert self.cache.size() == 2
