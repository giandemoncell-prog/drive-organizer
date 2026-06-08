from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from drive_organizer.drive.client import DriveClient


def _make_folder_item(fid: str, name: str) -> dict:
    return {"id": fid, "name": name, "mimeType": "application/vnd.google-apps.folder", "parents": ["root"]}


def _make_file_item(fid: str, name: str) -> dict:
    return {
        "id": fid,
        "name": name,
        "mimeType": "application/pdf",
        "size": "1024",
        "modifiedTime": "2024-06-15T12:00:00.000Z",
        "createdTime": "2024-03-10T09:00:00.000Z",
        "parents": ["d1"],
        "fileExtension": "pdf",
        "trashed": False,
        "ownedByMe": True,
        "capabilities": {"canMoveItemWithinDrive": True},
    }


def _make_service(folder_pages: list[list[dict]], file_pages: list[list[dict]]):
    """Build a mock Drive service routing by q-filter.

    list() returns a folder_req or file_req based on the mimeType filter in q.
    execute(http=...) returns the next response from the appropriate page iterator.
    """
    svc = MagicMock()
    svc._http.credentials = MagicMock()

    def _paged_responses(pages: list[list[dict]]) -> list[dict]:
        return [
            {"files": page, **({"nextPageToken": f"tok{i}"} if i < len(pages) - 1 else {})}
            for i, page in enumerate(pages)
        ]

    folder_responses = iter(_paged_responses(folder_pages))
    file_responses = iter(_paged_responses(file_pages))

    folder_req = MagicMock()
    file_req = MagicMock()
    folder_req.execute.side_effect = lambda http=None: next(folder_responses)
    file_req.execute.side_effect = lambda http=None: next(file_responses)

    def _list_side_effect(**kwargs):
        q = kwargs.get("q", "")
        if "mimeType='application/vnd.google-apps.folder'" in q:
            return folder_req
        return file_req

    svc.files.return_value.list.side_effect = _list_side_effect
    return svc


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_scan_returns_files_and_folder_map(mock_http_cls, mock_auth_cls):
    """scan_all_files returns files list and folder_map with correct ids."""
    svc = _make_service(
        [[_make_folder_item("d1", "Documents")]],
        [[_make_file_item("f1", "doc.pdf")]],
    )
    files, folder_map = DriveClient(svc).scan_all_files()

    assert len(files) == 1
    assert files[0].id == "f1"
    assert folder_map == {"d1": "Documents"}


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_scan_folders_not_in_files_list(mock_http_cls, mock_auth_cls):
    """Folder items go to folder_map only, not to files list."""
    svc = _make_service(
        [[_make_folder_item("d1", "Docs"), _make_folder_item("d2", "Images")]],
        [[]],
    )
    files, folder_map = DriveClient(svc).scan_all_files()

    assert files == []
    assert folder_map == {"d1": "Docs", "d2": "Images"}


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_clone_http_uses_service_credentials(mock_http_cls, mock_auth_cls):
    """_clone_http passes service credentials to AuthorizedHttp."""
    svc = MagicMock()
    fake_creds = MagicMock()
    svc._http.credentials = fake_creds

    DriveClient(svc)._clone_http()

    mock_auth_cls.assert_called_once_with(fake_creds, http=mock_http_cls.return_value)


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_clone_http_creates_fresh_transport_each_call(mock_http_cls, mock_auth_cls):
    """Each _clone_http call creates a distinct httplib2.Http instance."""
    svc = MagicMock()
    svc._http.credentials = MagicMock()
    client = DriveClient(svc)

    client._clone_http()
    client._clone_http()

    assert mock_http_cls.call_count == 2


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_scan_pagination_followed(mock_http_cls, mock_auth_cls):
    """scan_all_files follows nextPageToken across multiple pages."""
    svc = _make_service(
        [[_make_folder_item("d1", "A")], [_make_folder_item("d2", "B")]],
        [[_make_file_item("f1", "x.pdf")], [_make_file_item("f2", "y.pdf")]],
    )
    files, folder_map = DriveClient(svc).scan_all_files()

    assert len(files) == 2
    assert len(folder_map) == 2


@patch("google_auth_httplib2.AuthorizedHttp")
@patch("httplib2.Http")
def test_scan_advances_progress(mock_http_cls, mock_auth_cls):
    """Progress.advance is called once with total (files + folders) count."""
    svc = _make_service(
        [[_make_folder_item("d1", "Docs")]],
        [[_make_file_item("f1", "a.pdf"), _make_file_item("f2", "b.pdf")]],
    )
    progress = MagicMock()
    DriveClient(svc).scan_all_files(progress=progress, task_id=7)

    progress.advance.assert_called_once_with(7, 3)  # 2 files + 1 folder
