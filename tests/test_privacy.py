import pytest

from tests.helpers import make_file
from drive_organizer.ai.privacy import build_request, build_requests
from drive_organizer.ai.base import ClassificationRequest


def test_build_request_maps_metadata():
    f = make_file(id="f1", name="secret.pdf", mime_type="application/pdf",
                  size=12345, file_extension="pdf")
    req = build_request(f)
    assert isinstance(req, ClassificationRequest)
    assert req.file_id == "f1"
    assert req.name == "secret.pdf"
    assert req.mime_type == "application/pdf"
    assert req.size == 12345
    assert req.extension == "pdf"


def test_request_is_frozen():
    req = build_request(make_file())
    with pytest.raises(Exception):
        req.name = "tampered"  # type: ignore


def test_build_requests_preserves_order():
    files = [make_file(id=f"f{i}") for i in range(5)]
    reqs = build_requests(files)
    assert [r.file_id for r in reqs] == [f"f{i}" for i in range(5)]


def test_build_request_no_content_fields():
    f = make_file()
    req = build_request(f)
    assert not hasattr(req, "content")
    assert not hasattr(req, "text")
    assert not hasattr(req, "body")
