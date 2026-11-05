from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json_atomic


MANIFEST_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ManifestStore:
    def __init__(self, path: Path, project_dir: Path) -> None:
        self.path = path
        self.project_dir = project_dir.resolve()
        self._lock = threading.RLock()
        if path.is_file():
            self._data = read_json(path)
            if self._data.get("version") != MANIFEST_VERSION:
                raise ValueError(f"Unsupported production manifest version: {self._data.get('version')}")
        else:
            self._data = {
                "version": MANIFEST_VERSION,
                "project": self.project_dir.name,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "assets": {},
            }
        if not isinstance(self._data.get("assets"), dict):
            raise ValueError("production manifest assets must be an object")

    def save(self) -> None:
        with self._lock:
            self._data["updated_at"] = utc_now()
            write_json_atomic(self.path, self._data)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def get(self, asset_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._data["assets"].get(asset_id)
            return deepcopy(value) if isinstance(value, dict) else None

    def update(self, asset_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            record = self._data["assets"].setdefault(asset_id, {})
            if not isinstance(record, dict):
                raise ValueError(f"Invalid manifest record for {asset_id}")
            record.update(fields)
            record["updated_at"] = utc_now()
            self.save()
            return deepcopy(record)

    def increment_attempt(self, asset_id: str) -> int:
        with self._lock:
            record = self._data["assets"].setdefault(asset_id, {})
            attempts = int(record.get("attempts") or 0) + 1
            record["attempts"] = attempts
            record["updated_at"] = utc_now()
            self.save()
            return attempts

    def reset_for_retry(self, asset_id: str) -> None:
        with self._lock:
            record = self._data["assets"].get(asset_id)
            if not isinstance(record, dict):
                raise KeyError(asset_id)
            status = str(record.get("status") or "")
            idempotency_key = record.get("idempotency_key")
            provider = str(record.get("provider") or "")
            error_text = str(record.get("error") or "")
            explicit_no_charge = (
                provider == "flow"
                and "HTTP 402" in error_text
                and "Not enough credits" in error_text
            )
            if status == "submitted":
                raise ValueError(
                    f"Refusing to erase active remote state for {asset_id} ({status}); resume/reconcile it instead"
                )
            if status == "submitting" and idempotency_key:
                raise ValueError(
                    f"{asset_id} has a durable idempotency key; rerun normally so the same paid request is replayed safely"
                )
            if status == "uncertain" and idempotency_key and not explicit_no_charge:
                raise ValueError(
                    f"{asset_id} has a durable idempotency key; rerun normally so the same paid request is replayed safely"
                )
            if provider == "flow" and idempotency_key and not explicit_no_charge:
                raise ValueError(
                    f"{asset_id} is a completed/failed Flow creation identity and is not retried as a new creative attempt; create a separate candidate instead"
                )
            if status not in {"failed", "uncertain", "planned", "submitting"}:
                raise ValueError(f"Asset {asset_id} is not in a retryable state: {status or 'unset'}")
            history = record.setdefault("history", [])
            if not isinstance(history, list):
                raise ValueError(f"Asset {asset_id} retry history is invalid")
            snapshot = {
                key: deepcopy(value)
                for key, value in record.items()
                if key != "history"
            }
            snapshot["reset_at"] = utc_now()
            history.append(snapshot)
            for key in (
                "remote_job_id",
                "remote_status",
                "remote_request",
                "idempotency_key",
                "error",
                "output_sha256",
                "verified_at",
                "fingerprint",
                "references",
            ):
                record.pop(key, None)
            record["status"] = "planned"
            record["updated_at"] = utc_now()
            self.save()

