"""Regression tests for Google Drive upload safety behavior."""

from httplib2 import Response
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from src.adapters.google_drive import GoogleDriveAdapter


class _DummyDigest:
    date = "2026-05-11"


def _adapter_with_drive_service(existing_files, create_side_effect=None):
    adapter = GoogleDriveAdapter.__new__(GoogleDriveAdapter)
    adapter.folder_id = "folder123"

    drive_service = MagicMock()

    list_execute = MagicMock(return_value={"files": existing_files})
    drive_service.files.return_value.list.return_value.execute = list_execute

    create_execute = MagicMock()
    if create_side_effect is None:
        create_execute.return_value = {"id": "created123"}
    else:
        create_execute.side_effect = create_side_effect
    drive_service.files.return_value.create.return_value.execute = create_execute

    update_execute = MagicMock(return_value={})
    drive_service.files.return_value.update.return_value.execute = update_execute

    adapter.drive_service = drive_service
    adapter._digest_output_artifact = MagicMock(
        return_value=("Daily AI and Technology Digest - 2026-05-11.pdf", b"pdf-bytes", "application/pdf")
    )
    adapter._build_media_upload = MagicMock(return_value=object())

    return adapter, drive_service, list_execute, create_execute, update_execute


def _quota_http_error():
    return HttpError(
        resp=Response({"status": "403"}),
        content=b'{"error":{"errors":[{"reason":"storageQuotaExceeded"}]}}',
    )


def test_updates_existing_same_name_file():
    adapter, drive_service, _, _, update_execute = _adapter_with_drive_service(
        existing_files=[{"id": "existing456"}]
    )

    file_id = adapter._upload_or_update_file(_DummyDigest())

    assert file_id == "existing456"
    drive_service.files.return_value.update.assert_called_once()
    drive_service.files.return_value.create.assert_not_called()
    assert update_execute.call_count == 1


def test_create_quota_failure_does_not_rename_or_update_latest_file():
    adapter, drive_service, _, create_execute, update_execute = _adapter_with_drive_service(
        existing_files=[],
        create_side_effect=_quota_http_error(),
    )

    with pytest.raises(RuntimeError, match="drive_storage_quota_exceeded"):
        adapter._upload_or_update_file(_DummyDigest())

    assert create_execute.call_count == 1
    # No update fallback should run on quota failure.
    drive_service.files.return_value.update.assert_not_called()
    assert update_execute.call_count == 0
