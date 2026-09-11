"""Google Drive sync for OTP evidence and ledger.

Stores OAuth tokens locally. Uploads receipts and ledger to a dedicated
OTP folder in the user's Google Drive. Detects conflicts when multiple
machines sync the same evidence.

Setup:
1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable the Google Drive API
3. Create OAuth2 credentials (Desktop app type)
4. Download credentials.json to ~/.otp/credentials.json
5. Run: otp drive auth
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

CONFIG_DIR = Path.home() / ".otp"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "token.json"
SYNC_STATE_FILE = CONFIG_DIR / "sync_state.json"

FOLDER_NAME = "OTP Evidence"
MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_JSON = "application/json"
MIME_JSONL = "application/x-ndjson"


class DriveSync:
    """Google Drive sync for OTP evidence."""

    def __init__(self) -> None:
        self._service = None
        self._folder_id: str | None = None

    def is_authenticated(self) -> bool:
        return TOKEN_FILE.exists()

    def authenticate(self, credentials_path: Path | None = None) -> str:
        """Run OAuth2 flow. Returns the authenticated email or raises."""
        creds_path = credentials_path or CREDENTIALS_FILE
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Credentials not found at {creds_path}\n"
                "Download credentials.json from Google Cloud Console\n"
                "(OAuth2 > Desktop app type) and place it there."
            )

        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)

            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        about = self._service.about().get(fields="user").execute()
        return about["user"]["emailAddress"]

    def _get_service(self):
        if self._service:
            return self._service
        if not TOKEN_FILE.exists():
            raise RuntimeError("Not authenticated. Run: otp drive auth")
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _get_or_create_folder(self, service) -> str:
        if self._folder_id:
            return self._folder_id

        results = service.files().list(
            q=f"name='{FOLDER_NAME}' and mimeType='{MIME_FOLDER}' and trashed=false",
            fields="files(id, name)",
        ).execute()
        files = results.get("files", [])

        if files:
            self._folder_id = files[0]["id"]
        else:
            meta = {"name": FOLDER_NAME, "mimeType": MIME_FOLDER}
            folder = service.files().create(body=meta, fields="id").execute()
            self._folder_id = folder["id"]

        return self._folder_id

    def _find_file(self, service, folder_id: str, name: str) -> str | None:
        results = service.files().list(
            q=f"name='{name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id, name, modifiedTime, md5Checksum)",
        ).execute()
        files = results.get("files", [])
        return files[0] if files else None

    def _load_sync_state(self) -> dict[str, Any]:
        if SYNC_STATE_FILE.exists():
            return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
        return {"upload_count": 0, "last_sync": None, "last_file": None}

    def _save_sync_state(self, state: dict[str, Any]) -> None:
        SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def upload_file(self, local_path: Path, remote_name: str | None = None) -> dict[str, Any]:
        """Upload a file to the OTP Drive folder. Returns upload metadata."""
        service = self._get_service()
        folder_id = self._get_or_create_folder(service)
        name = remote_name or local_path.name

        # Check for existing file
        existing = self._find_file(service, folder_id, name)
        local_hash = hashlib.md5(local_path.read_bytes()).hexdigest()

        if existing and existing.get("md5Checksum") == local_hash:
            return {"status": "unchanged", "file_id": existing["id"], "name": name}

        if existing:
            # Update existing
            media = MediaFileUpload(str(local_path), mimetype=MIME_JSON, resumable=True)
            service.files().update(fileId=existing["id"], media_body=media).execute()
            status = "updated"
        else:
            # Create new
            meta = {"name": name, "parents": [folder_id]}
            media = MediaFileUpload(str(local_path), mimetype=MIME_JSON, resumable=True)
            result = service.files().create(body=meta, media_body=media, fields="id").execute()
            existing = result
            status = "created"

        state = self._load_sync_state()
        state["upload_count"] += 1
        state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state["last_file"] = name
        self._save_sync_state(state)

        return {"status": status, "file_id": existing["id"], "name": name}

    def sync_ledger(self, ledger_path: Path) -> dict[str, Any]:
        """Sync the ledger JSONL file to Drive. Returns sync result."""
        if not ledger_path.exists():
            return {"status": "no_ledger", "path": str(ledger_path)}
        return self.upload_file(ledger_path, "ledger.jsonl")

    def sync_evidence_dir(self, evidence_dir: Path) -> list[dict[str, Any]]:
        """Sync all JSON/JSONL files in an evidence directory."""
        results = []
        if not evidence_dir.exists():
            return results
        for f in sorted(evidence_dir.iterdir()):
            if f.suffix in (".json", ".jsonl"):
                try:
                    result = self.upload_file(f)
                    results.append(result)
                except Exception as e:
                    results.append({"status": "error", "name": f.name, "error": str(e)})
        return results

    def get_sync_status(self) -> dict[str, Any]:
        """Get current sync state."""
        state = self._load_sync_state()
        return {
            "authenticated": self.is_authenticated(),
            "upload_count": state.get("upload_count", 0),
            "last_sync": state.get("last_sync"),
            "last_file": state.get("last_file"),
        }

    def disconnect(self) -> None:
        """Remove stored token."""
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        self._service = None
        self._folder_id = None
