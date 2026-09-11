"""Tests for Drive sync (mocked — no real Google API calls)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from otp.drive_sync import DriveSync, CONFIG_DIR, TOKEN_FILE, SYNC_STATE_FILE


@pytest.fixture
def tmp_config(tmp_path):
    """Redirect config dir to a temp directory."""
    with patch("otp.drive_sync.CONFIG_DIR", tmp_path), \
         patch("otp.drive_sync.TOKEN_FILE", tmp_path / "token.json"), \
         patch("otp.drive_sync.SYNC_STATE_FILE", tmp_path / "sync_state.json"):
        yield tmp_path


class TestDriveSyncStatus:
    def test_not_authenticated(self, tmp_config):
        ds = DriveSync()
        assert ds.is_authenticated() is False

    def test_authenticated_when_token_exists(self, tmp_config):
        (tmp_config / "token.json").write_text(json.dumps({
            "token": "fake",
            "refresh_token": "fake",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake",
            "client_secret": "fake",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        }))
        ds = DriveSync()
        assert ds.is_authenticated() is True

    def test_get_sync_status_empty(self, tmp_config):
        ds = DriveSync()
        status = ds.get_sync_status()
        assert status["authenticated"] is False
        assert status["upload_count"] == 0
        assert status["last_sync"] is None

    def test_disconnect_removes_token(self, tmp_config):
        (tmp_config / "token.json").write_text("{}")
        ds = DriveSync()
        assert ds.is_authenticated() is True
        ds.disconnect()
        assert ds.is_authenticated() is False


class TestDriveSyncUpload:
    def test_upload_file_creates_new(self, tmp_config):
        ds = DriveSync()
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {"files": []}
        mock_service.files().create().execute.return_value = {"id": "new_file_id"}
        ds._service = mock_service
        ds._folder_id = "folder_123"

        test_file = tmp_config / "test_receipt.json"
        test_file.write_text(json.dumps({"test": "data"}))

        result = ds.upload_file(test_file)
        assert result["status"] == "created"
        assert result["file_id"] == "new_file_id"
        assert result["name"] == "test_receipt.json"

    def test_upload_file_unchanged(self, tmp_config):
        ds = DriveSync()
        import hashlib
        test_data = json.dumps({"test": "data"}).encode()
        md5_hash = hashlib.md5(test_data).hexdigest()

        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "existing_id", "md5Checksum": md5_hash}]
        }
        ds._service = mock_service
        ds._folder_id = "folder_123"

        test_file = tmp_config / "test_receipt.json"
        test_file.write_bytes(test_data)

        result = ds.upload_file(test_file)
        assert result["status"] == "unchanged"

    def test_upload_file_updates_existing(self, tmp_config):
        ds = DriveSync()
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "existing_id", "md5Checksum": "old_hash"}]
        }
        ds._service = mock_service
        ds._folder_id = "folder_123"

        test_file = tmp_config / "test_receipt.json"
        test_file.write_text(json.dumps({"updated": "data"}))

        result = ds.upload_file(test_file)
        assert result["status"] == "updated"

    def test_sync_ledger_no_file(self, tmp_config):
        ds = DriveSync()
        result = ds.sync_ledger(tmp_config / "nonexistent.jsonl")
        assert result["status"] == "no_ledger"

    def test_sync_evidence_dir_empty(self, tmp_config):
        ds = DriveSync()
        results = ds.sync_evidence_dir(tmp_config / "empty_dir")
        assert results == []


class TestDriveSyncState:
    def test_sync_state_persists(self, tmp_config):
        ds = DriveSync()
        state = ds._load_sync_state()
        assert state["upload_count"] == 0

        state["upload_count"] = 5
        ds._save_sync_state(state)

        loaded = ds._load_sync_state()
        assert loaded["upload_count"] == 5
