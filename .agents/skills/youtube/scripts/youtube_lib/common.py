from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
SUPPORTED_THUMBNAIL_SUFFIXES = {".png", ".jpg", ".jpeg"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_google_libs() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ModuleNotFoundError:
        die(
            "missing Google API libraries. Install with: "
            "python3 -m pip install --user google-api-python-client "
            "google-auth-oauthlib google-auth-httplib2"
        )
    return Request, Credentials, InstalledAppFlow, build, HttpError, MediaFileUpload


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"missing required file: {path}")
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def video_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if host.endswith("youtu.be") and path_parts:
        return path_parts[0]
    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            return path_parts[1]

    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)

    die(f"could not parse YouTube video id from: {value}")


def parse_channel_handle(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.netloc:
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0].startswith("@"):
            return parts[0]
        if len(parts) >= 2 and parts[0] in {"channel", "c", "user"}:
            return parts[1]
    return value
