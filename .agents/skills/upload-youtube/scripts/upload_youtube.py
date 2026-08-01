#!/usr/bin/env python3
"""Upload a Story Video Maker project to YouTube.

This script intentionally lives inside the upload-youtube skill. It does not
depend on project src/ code so the upload capability can remain skill-owned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube"
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024


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
    except ModuleNotFoundError as exc:
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


def write_upload_json(project_dir: Path, payload: dict[str, Any]) -> Path:
    out = project_dir / "youtube" / "upload.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def project_paths(project_dir: Path) -> dict[str, Path]:
    return {
        "video": project_dir / "output" / "final-video.mp4",
        "youtube_dir": project_dir / "youtube",
        "metadata": project_dir / "youtube" / "metadata.json",
        "upload": project_dir / "youtube" / "upload.json",
        "thumbnails": project_dir / "youtube" / "thumbnails",
    }


def normalize_project_dir(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.exists():
        die(f"project folder does not exist: {p}")
    if not p.is_dir():
        die(f"project path is not a folder: {p}")
    return p


def select_thumbnail(thumbnails_dir: Path) -> tuple[Path | None, str | None]:
    candidates: list[Path] = []
    for name in ("thumbnail-01.png", "thumbnail-01.jpg", "thumbnail-01.jpeg"):
        candidates.append(thumbnails_dir / name)
    if thumbnails_dir.exists():
        candidates.extend(
            sorted(
                p
                for p in thumbnails_dir.iterdir()
                if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
            )
        )

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists() or not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        size = path.stat().st_size
        if size > THUMBNAIL_MAX_BYTES:
            return None, f"thumbnail too large for YouTube API (max 2 MB): {path}"
        return path, None

    return None, "no thumbnail image found"


def token_path(scope_profile: str) -> Path:
    config_dir = Path.home() / ".config" / "projects"
    if scope_profile == "upload":
        legacy = config_dir / "youtube_token.json"
        if legacy.exists():
            return legacy
        return config_dir / "youtube_token_upload.json"
    if scope_profile == "manage":
        return config_dir / "youtube_token_manage.json"
    die(f"unknown scope profile: {scope_profile}")


def get_credentials(scope_profile: str):
    Request, Credentials, InstalledAppFlow, *_ = load_google_libs()
    config_dir = Path.home() / ".config" / "projects"
    client_secret = config_dir / "youtube_client_secret.json"
    if not client_secret.exists():
        die(f"missing OAuth client secret: {client_secret}")

    scopes = [UPLOAD_SCOPE] if scope_profile == "upload" else [MANAGE_SCOPE]
    token = token_path(scope_profile)

    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def youtube_client(scope_profile: str):
    *_, build, _, _ = load_google_libs()
    return build("youtube", "v3", credentials=get_credentials(scope_profile))


def metadata_body(metadata: dict[str, Any], visibility: str) -> dict[str, Any]:
    title = metadata.get("recommended_title") or metadata.get("title")
    description = metadata.get("description")
    if not title:
        die("metadata.json must include recommended_title or title")
    if not description:
        die("metadata.json must include description")

    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        tags = []

    snippet: dict[str, Any] = {
        "title": str(title)[:100],
        "description": str(description)[:5000],
        "categoryId": str(metadata.get("categoryId") or metadata.get("category_id") or "22"),
    }
    if tags:
        snippet["tags"] = [str(t) for t in tags][:30]

    return {
        "snippet": snippet,
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": bool(metadata.get("selfDeclaredMadeForKids", False)),
        },
    }


def upload_thumbnail(youtube, video_id: str, thumbnail: Path | None) -> dict[str, Any] | None:
    if thumbnail is None:
        return None
    *_, MediaFileUpload = load_google_libs()
    mime_type = mimetypes.guess_type(str(thumbnail))[0] or "image/png"
    media = MediaFileUpload(str(thumbnail), mimetype=mime_type, resumable=False)
    return youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def command_upload(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)

    if paths["upload"].exists() and not args.force:
        print(f"upload_json_exists {paths['upload']}")
        print("not re-uploading; checking status instead")
        command_status(args)
        return

    video_path = paths["video"]
    if not video_path.exists():
        die(f"missing final video: {video_path}")

    metadata = read_json(paths["metadata"])
    body = metadata_body(metadata, args.visibility)
    thumbnail, thumbnail_warning = select_thumbnail(paths["thumbnails"])

    youtube = youtube_client("upload")
    *_, HttpError, MediaFileUpload = load_google_libs()
    media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"upload_progress {int(status.progress() * 100)}%")
    except HttpError as exc:
        payload = {
            "state": "failed",
            "operation": "upload",
            "failed_at": utc_now(),
            "project": str(project_dir),
            "video_path": str(video_path),
            "visibility": args.visibility,
            "error": str(exc),
            "status_code": getattr(exc.resp, "status", None),
        }
        out = write_upload_json(project_dir, payload)
        print(f"upload_failed {out}")
        raise

    video_id = response.get("id")
    if not video_id:
        die("YouTube upload response did not include a video id")

    thumbnail_response = None
    thumbnail_error = None
    if thumbnail is not None:
        try:
            thumbnail_response = upload_thumbnail(youtube, video_id, thumbnail)
        except Exception as exc:  # Keep video upload success even if thumbnail fails.
            thumbnail_error = str(exc)

    payload = {
        "state": "uploaded",
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "visibility": args.visibility,
        "processing_status": "unknown",
        "project": str(project_dir),
        "video_path": str(video_path),
        "video_sha256": sha256_file(video_path),
        "metadata_path": str(paths["metadata"]),
        "metadata_sha256": sha256_json(metadata),
        "thumbnail_path": str(thumbnail) if thumbnail else None,
        "thumbnail_sha256": sha256_file(thumbnail) if thumbnail else None,
        "thumbnail_warning": thumbnail_warning,
        "thumbnail_error": thumbnail_error,
        "uploaded_at": utc_now(),
        "last_checked_at": None,
        "youtube_response": response,
        "thumbnail_response": thumbnail_response,
    }
    out = write_upload_json(project_dir, payload)
    print("upload_accepted True")
    print(f"video_id {video_id}")
    print(f"url https://youtu.be/{video_id}")
    print(f"visibility {args.visibility}")
    print(f"saved {out}")
    if thumbnail_error:
        print(f"thumbnail_failed {thumbnail_error}")
    elif thumbnail:
        print(f"thumbnail_set {thumbnail}")
    else:
        print(f"thumbnail_skipped {thumbnail_warning}")


def command_status(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)
    if not paths["upload"].exists():
        die(f"missing upload state: {paths['upload']}")

    payload = read_json(paths["upload"])
    video_id = payload.get("video_id")
    if not video_id:
        die(f"upload.json does not contain video_id: {paths['upload']}")

    youtube = youtube_client("manage")
    response = youtube.videos().list(part="snippet,status,processingDetails", id=video_id).execute()
    items = response.get("items", [])
    item = items[0] if items else None
    status = item.get("status", {}) if item else {}
    processing = item.get("processingDetails", {}) if item else {}

    payload.update(
        {
            "state": "status_checked" if item else "not_found",
            "last_checked_at": utc_now(),
            "visibility": status.get("privacyStatus", payload.get("visibility")),
            "upload_status": status.get("uploadStatus"),
            "processing_status": processing.get("processingStatus", "unknown" if item else "not_found"),
            "status_response": response,
        }
    )
    out = write_upload_json(project_dir, payload)
    print(f"video_id {video_id}")
    print(f"url {payload.get('url')}")
    print(f"state {payload['state']}")
    print(f"visibility {payload.get('visibility')}")
    print(f"upload_status {payload.get('upload_status')}")
    print(f"processing_status {payload.get('processing_status')}")
    print(f"saved {out}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload or check a Story Video Maker YouTube package.")
    sub = parser.add_subparsers(dest="command", required=True)

    upload = sub.add_parser("upload", help="Upload the project video once and write upload.json.")
    upload.add_argument("project_dir", help="Path like library/<project_slug>")
    upload.add_argument("--visibility", choices=["private", "unlisted", "public"], default="private")
    upload.add_argument("--force", action="store_true", help="Force a new upload even if upload.json exists.")
    upload.set_defaults(func=command_upload)

    status = sub.add_parser("status", help="Check an existing upload and update upload.json.")
    status.add_argument("project_dir", help="Path like library/<project_slug>")
    status.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    status.set_defaults(func=command_status, visibility=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
